#!/usr/bin/env python3
"""
giornata.py - Ricostruisce la giornata lavorativa e la ripartisce per commessa.

Modello (ricavato confrontando i dati con le ricostruzioni a mano di Matteo):

  ore in postazione = ultima attivita' - prima attivita' - pausa pranzo

La pausa si legge dal bucket AFK, non dai buchi tra le finestre: il 04/08 la
finestra di Desktop Remoto e' rimasta in primo piano per tutta la pausa,
simulando lavoro, mentre l'AFK segnava correttamente 89 minuti di assenza.
Verificato su due giornate indipendenti: 04/08 -> 7h54, 24/06 -> 8h05.

Il tempo NON viene intersecato con l'AFK: leggere uno schema o guardare un
ciclo macchina e' lavoro anche senza toccare il mouse.

    python giornata.py --giorno 2026-06-24 --out foglio.md
    python giornata.py --mese 2026-06 --out log/2026-06.md
"""

import argparse
import collections
import json
import os
import re
import sys
from datetime import datetime, timedelta, date

import aw_report as AW

GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

PAUSA_DEFAULT = timedelta(minutes=90)    # dichiarata da Matteo: sempre, tipicamente 1h30
PAUSA_MINIMA = timedelta(minutes=60)
PAUSA_MASSIMA = timedelta(hours=3)       # oltre, non e' pausa: e' fine giornata
FASCIA_PAUSA = (11.0, 15.5)              # ore decimali in cui cercare la pausa
UNIONE_BLOCCO = timedelta(minutes=5)     # stesso programma entro 5 min = stesso blocco
BLOCCO_MINIMO = timedelta(minutes=2)
EREDITA_MAX = timedelta(minutes=60)      # oltre, non si eredita: diventa "Altro"


# ------------------------------------------------------------------ utilita'
def hm(td):
    m = round(td.total_seconds() / 60)
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"


def ore(td):
    return td.total_seconds() / 3600


def dt(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone()


def unisci(intervalli):
    out = []
    for s, e in sorted(intervalli):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(a, b) for a, b in out]


# --------------------------------------------------------------- categorie
def carica_categorie():
    """Le categorie sono quelle che Matteo ha definito nella UI di ActivityWatch.
    Non vanno duplicate qui: se una app non e' coperta resta 'Non categorizzato',
    ed e' un'informazione utile, non un buco da tappare."""
    try:
        s = json.load(open(AW.DB.replace("peewee-sqlite.v2.db", "settings.json"),
                           encoding="utf-8"))
    except OSError:
        return []
    out = []
    for c in s.get("classes", []):
        r = c.get("rule") or {}
        if r.get("type") == "regex" and r.get("regex"):
            try:
                out.append((c["name"], re.compile(r["regex"],
                                                  0 if r.get("ignore_case") is False else re.I)))
            except re.error:
                pass
    return out


def categoria(classi, app, titolo):
    best = None
    for nome, rx in classi:
        if rx.search(f"{app} {titolo}") and (best is None or len(nome) > len(best)):
            best = nome
    return " > ".join(best) if best else "Non categorizzato"


# ------------------------------------------------------------------ blocchi
def blocchi_giorno(eventi):
    """Eventi contigui dello stesso programma diventano un blocco unico."""
    out = []
    # Ordinamento sul tempo, non sulla stringa: l'API scrive '...T10:00...' e
    # SQLite '... 10:00...', e mescolando le due sorgenti (host + VM) un
    # confronto testuale metterebbe gli eventi nell'ordine sbagliato.
    for e in sorted(eventi, key=lambda x: dt(x["timestamp"])):
        app = e["data"].get("app") or ""
        if app.lower() in AW.SISTEMA or e["duration"] < 1:
            continue
        s = dt(e["timestamp"])
        f = s + timedelta(seconds=e["duration"])
        if out and out[-1]["app"] == app and s - out[-1]["fine"] <= UNIONE_BLOCCO:
            b = out[-1]
            b["fine"] = max(b["fine"], f)
            b["durata"] += timedelta(seconds=e["duration"])
            b["titoli"][e["data"].get("title") or ""] += e["duration"]
        else:
            out.append({"app": app, "inizio": s, "fine": f,
                        "durata": timedelta(seconds=e["duration"]),
                        "titoli": collections.Counter({e["data"].get("title") or "": e["duration"]})})
    return [b for b in out if b["durata"] >= BLOCCO_MINIMO]


# Prima delle 7 e dopo le 20 non e' lavoro, per dichiarazione esplicita di
# Matteo: qualunque finestra in quella fascia (mail letta a letto, un
# programma rimasto acceso) non deve mai comparire ne' nella scaletta ne' nel
# totale della giornata.
ORARIO_MIN, ORARIO_MAX = 7, 20


def clip_orario(blocchi):
    out = []
    for b in blocchi:
        lo = max(b["inizio"], b["inizio"].replace(hour=ORARIO_MIN, minute=0, second=0, microsecond=0))
        hi = min(b["fine"], b["inizio"].replace(hour=ORARIO_MAX, minute=0, second=0, microsecond=0))
        if hi <= lo:
            continue
        if lo == b["inizio"] and hi == b["fine"]:
            out.append(b)
        else:
            b2 = dict(b)
            b2["inizio"], b2["fine"] = lo, hi
            b2["durata"] = hi - lo
            out.append(b2)
    return out


def cornice(blocchi, afk_events):
    """Inizio, fine e pausa della giornata."""
    assenze = unisci([(dt(a["timestamp"]),
                       dt(a["timestamp"]) + timedelta(seconds=a["duration"]))
                      for a in afk_events if a["data"].get("status") == "afk"
                      and a["duration"] > 0])
    inizio = blocchi[0]["inizio"]
    fine = max(b["fine"] for b in blocchi)
    pausa, dedotta = None, False
    for a, b in assenze:
        h = a.hour + a.minute / 60
        # Il bucket AFK riporta la durata VERA di un'assenza, anche quando dura
        # giorni (weekend, ponte, malattia): se Matteo si ferma a mezzogiorno di
        # venerdi' e torna martedi', quell'assenza inizia in fascia pausa ma non
        # e' una pausa pranzo. Sopra le 3 ore non e' pausa, e' fine giornata: la
        # si scarta e "fine" resta l'ultimo blocco reale prima dell'assenza.
        if FASCIA_PAUSA[0] <= h <= FASCIA_PAUSA[1] and PAUSA_MINIMA <= (b - a) <= PAUSA_MASSIMA:
            if pausa is None or (b - a) > (pausa[1] - pausa[0]):
                pausa = (a, b)
    if pausa is None and inizio <= inizio.replace(hour=12, minute=30, second=0, microsecond=0) \
            and fine >= inizio.replace(hour=12, minute=30, second=0, microsecond=0) + PAUSA_DEFAULT:
        # Matteo la pausa la fa sempre: se i dati non la mostrano e' perche' una
        # finestra e' rimasta in primo piano, non perche' abbia lavorato. Ma vale
        # solo se la giornata attraversa davvero il mezzogiorno: un giorno che
        # inizia alle 15:47 non ha una pausa pranzo da dedurre, ne' prima ne' dopo.
        mezzo = inizio.replace(hour=12, minute=30, second=0, microsecond=0)
        pausa, dedotta = (mezzo, mezzo + PAUSA_DEFAULT), True
    durata_pausa = (pausa[1] - pausa[0]) if pausa else timedelta()
    if pausa is None:
        pausa = (fine, fine)   # segnaposto a durata zero, per il resto del codice
    return {"inizio": inizio, "fine": fine, "pausa": pausa, "pausa_dedotta": dedotta,
            "lavorate": (fine - inizio) - durata_pausa}


# -------------------------------------------------------------- attribuzione
# Una commessa vive su una piattaforma sola. Se il blocco parla di Beckhoff
# mentre la commessa accanto e' Omron, non e' lavoro su quella commessa: e'
# ricerca o formazione, e va tenuta separata. Regola verificata sul 24/06, dove
# mezz'ora di documentazione TwinCAT stava in mezzo a due commesse Sysmac.
PIATTAFORME = {
    "Beckhoff/TwinCAT": re.compile(r"(?i)twincat|beckhoff|tcxae|\bads\b|ethercat"),
    "Omron/Sysmac": re.compile(r"(?i)sysmac|omron|\bnj\d|\bnx\d|cx-p"),
    "Siemens/TIA": re.compile(r"(?i)tia portal|siemens|step ?7|\bs7-"),
}


def piattaforma(app, titolo):
    for nome, rx in PIATTAFORME.items():
        if rx.search(f"{app} {titolo}"):
            return nome
    return None


# Attivita' che non appartengono a nessuna commessa e che quindi non devono
# ereditarne una, per quanto siano vicine nel tempo a del lavoro vero. Senza
# questo filtro il 04/08 la spesa personale e Telegram, interlacciati con il
# Desktop Remoto, finivano dentro la commessa: 7h30 invece di 4h.
PERSONALE = re.compile(r"(?i)ballanmatteo@gmail|whatsapp|telegram|youtube|"
                       r"paga in \d rate|checkout|carrello|amazon|subito\.it|"
                       r"offerte di lavoro|linkedin|meteo|hotel |booking|prenotaz")
CAT_PERSONALI = ("Media",)


def e_personale(cat, app, titolo, extra):
    if cat.startswith(CAT_PERSONALI) or cat == "Comms > IM":
        return True
    if PERSONALE.search(f"{app} {titolo}"):
        return True
    return any(rx.search(f"{app} {titolo}") for rx in extra)


def compila_contesti(cfg):
    """Ambienti che non dichiarano il progetto nel titolo.

    Un Desktop Remoto mostra l'indirizzo IP, una macchina virtuale il proprio
    nome: dall'host il progetto aperto dentro non e' visibile. Il collegamento
    'quell'IP e' quella commessa' puo' farlo solo Matteo, e va scritto nella
    configurazione. Le finestre di validita' servono perche' una VM cambia
    progetto nel tempo."""
    out = []
    for c in cfg.get("contesti", []):
        try:
            out.append((re.compile(c["pattern"], re.I), c["commessa"],
                        date.fromisoformat(c["da"]) if c.get("da") else None,
                        date.fromisoformat(c["a"]) if c.get("a") else None))
        except (re.error, KeyError, ValueError):
            print(f"  contesto ignorato (malformato): {c}", file=sys.stderr)
    return out


def compila_vm(cfg, base):
    """Macchine virtuali con un ActivityWatch proprio dentro.

    'db' e' il percorso della copia del database, relativo alla cartella di
    commesse.json. 'pattern' individua sull'host la finestra di QUELLA VM, non
    una qualsiasi: sul PC di Matteo gira anche una seconda macchina virtuale, e
    sostituire il suo tempo coi dati della VM sbagliata sposterebbe ore da una
    commessa all'altra. 'da' protegge i mesi gia' consuntivati prima che il
    watcher esistesse."""
    out = []
    for v in cfg.get("vm", []):
        try:
            db = os.path.join(base, v["db"])
            rx = re.compile(v["pattern"], re.I)
            da = date.fromisoformat(v["da"]) if v.get("da") else None
            a = date.fromisoformat(v["a"]) if v.get("a") else None
        except (re.error, KeyError, ValueError):
            print(f"  vm ignorata (malformata): {v}", file=sys.stderr)
            continue
        if not os.path.exists(db):
            # Il file lo copia Matteo a mano una volta al mese: se manca, il
            # report esce lo stesso coi soli dati dell'host, ma va detto forte.
            print(f"  ATTENZIONE: copia della VM assente ({db}): le ore dentro "
                  f"{v['pattern']} restano non dettagliate.", file=sys.stderr)
            continue
        out.append((db, rx, da, a))
    return out


def attribuisci(blocchi, mappa, contesti=(), classi=(), personali=()):
    """Prima il titolo, poi i contesti dichiarati, infine la vicinanza.

    Un blocco senza commessa eredita quella dell'ancora piu' vicina nel tempo:
    lavorare su una commessa significa anche leggere la mail, aprire lo schema e
    chiedere all'LLM, e quel tempo appartiene alla commessa."""
    for b in blocchi:
        t = b["titoli"].most_common(1)[0][0]
        codici = [c for c, _ in AW.estrai_candidati(t) if c in mappa]
        if not codici:
            codici = [c for c in AW.P_CODE_SOLO.findall(AW.pulisci(t)) if AW.norm_code(c) in mappa]
            codici = [AW.norm_code(c) for c in codici]
        b["commessa"] = f"{codici[0]} {mappa[codici[0]]}" if codici else None
        b["ancora"] = bool(codici)
        if not b["ancora"]:
            g = b["inizio"].date()
            for rx, com, da, a in contesti:
                if rx.search(f"{b['app']} {t}") and (da is None or g >= da) and (a is None or g <= a):
                    b["commessa"], b["ancora"], b["contesto"] = com, True, True
                    break
        b["piattaforma"] = piattaforma(b["app"], t)
        b["personale"] = (not b["ancora"] and
                          e_personale(categoria(classi, b["app"], t), b["app"], t, personali))

    # Piattaforma di ciascuna commessa, dedotta dalle ancore della giornata.
    piat_com = {}
    for b in blocchi:
        if b["ancora"] and b["piattaforma"]:
            piat_com.setdefault(b["commessa"], b["piattaforma"])

    ancore = [i for i, b in enumerate(blocchi) if b["ancora"]]
    # Un ambiente di sviluppo aperto e' sempre lavoro su una commessa, anche
    # quando la finestra non ne dichiara il nome ("Auto Connect Project" di
    # Sysmac). Vale come prova per la commessa piu' vicina della stessa
    # piattaforma: un progetto Omron non si apre in TwinCAT.
    for i, b in enumerate(blocchi):
        if b["ancora"] or AW.APP2CAT.get(b["app"].lower()) not in AW.SVILUPPO:
            continue
        cand = [(abs(j - i), blocchi[j]["commessa"]) for j, x in enumerate(blocchi)
                if x["ancora"] and x["commessa"]
                and (not b["piattaforma"] or piat_com.get(x["commessa"]) in (None, b["piattaforma"]))]
        if cand:
            b["commessa"], b["ancora"], b["debole"] = min(cand)[1], True, True

    for i, b in enumerate(blocchi):
        if b["ancora"] or b["personale"]:
            continue
        prima = max((j for j in ancore if j < i), default=None)
        dopo = min((j for j in ancore if j > i), default=None)
        dp = b["inizio"] - blocchi[prima]["fine"] if prima is not None else None
        dd = blocchi[dopo]["inizio"] - b["fine"] if dopo is not None else None
        scelto = None
        if dp is not None and (dd is None or dp <= dd):
            scelto = prima if dp <= EREDITA_MAX else None
        elif dd is not None:
            scelto = dopo if dd <= EREDITA_MAX else None
        if scelto is None:
            continue
        cand = blocchi[scelto]["commessa"]
        if b["piattaforma"] and piat_com.get(cand) and piat_com[cand] != b["piattaforma"]:
            b["commessa"] = f"Ricerca {b['piattaforma']}"
            b["ricerca"] = True
        else:
            b["commessa"] = cand
        b["dedotta"] = True

    # I blocchi neutri (browser, mail) stretti fra due blocchi di ricerca fanno
    # parte della stessa ricerca: da soli non direbbero nulla.
    for i, b in enumerate(blocchi):
        if b.get("ricerca") or b["ancora"] or not b.get("dedotta"):
            continue
        vicini = [blocchi[j].get("commessa") for j in (i - 1, i + 1)
                  if 0 <= j < len(blocchi) and blocchi[j].get("ricerca")]
        if len(vicini) == 2 and vicini[0] == vicini[1]:
            b["commessa"], b["ricerca"] = vicini[0], True
    return blocchi


PASSO = timedelta(minutes=10)


def ripartisci(blocchi, c):
    """La giornata si divide in slot di 10 minuti, ciascuno alla voce prevalente.

    Votano solo i blocchi che portano una prova: un codice commessa nel titolo,
    un contesto dichiarato (l'IP del Desktop Remoto), una ricerca su un'altra
    piattaforma, o un'attivita' dichiaratamente personale. Tutto il resto -
    'Claude', un PDF, una cartella - resta muto e si accoda a chi ha vinto la
    finestra di 10 minuti.

    Sostituisce l'ereditarieta' a 60 minuti: quella, sui giorni densi, tirava
    ore estranee dentro la commessa piu' vicina (04/08: 7h di SMEG contro 5h)."""
    p0, p1 = c["pausa"]
    slot, t = [], c["inizio"]
    while t < c["fine"]:
        t2 = min(t + PASSO, c["fine"])
        # I bordi della pausa possono tagliare uno slot: votano solo i minuti netti.
        for lo, hi in ((t, min(t2, p0)), (max(t, p1), t2)):
            if hi > lo:
                slot.append([lo, hi, collections.Counter()])
        t = t2
    for b in blocchi:
        voce = "Altro" if b.get("personale") else (
            b["commessa"] if (b.get("ancora") or b.get("ricerca")) else None)
        if not voce:
            continue
        for s in slot:
            lo, hi = max(b["inizio"], s[0]), min(b["fine"], s[1])
            if hi > lo:
                s[2][voce] += (hi - lo).total_seconds()
    totale, presenze = collections.Counter(), collections.Counter()
    for s in slot:
        totale.update(s[2])
        presenze.update(s[2].keys())
    # Una commessa con pochi minuti di prove nella giornata resta nel conto -
    # e' pur sempre lavoro fatto - ma tiene solo le slot di 10 minuti in cui compare
    # davvero: non si prende anche quelle mute intorno. Cosi' una capatina di
    # dieci minuti mantiene il proprio slot, senza assorbire quello muto.
    deboli = {k for k, v in totale.items() if v < 900 and k != "Altro"}

    vinti = [max(s[2], key=s[2].get) if s[2] else None for s in slot]
    for i, v in enumerate(vinti):
        if not v:   # finestra di 10 minuti senza prove: si accoda alla piu' vicina che ne ha
            vicini = [(abs(j - i), j) for j in range(len(vinti))
                      if vinti[j] and vinti[j] not in deboli]
            vinti[i] = vinti[min(vicini)[1]] if vicini else "Altro"
    out = collections.Counter()
    for s, v in zip(slot, vinti):
        out[v] += (s[1] - s[0]).total_seconds() / 3600
    mute = sum(1 for s in slot if not s[2]) / len(slot) if slot else 0
    # L'ultima finestra di 10 minuti della giornata e' quasi sempre parziale: arrotondare
    # ogni voce per conto suo farebbe sforare il totale.
    return out, round(mute, 2)


def arrotonda(voci, totale, passo=0.5):
    """Arrotonda a mezz'ora facendo comunque tornare la somma: si assegna prima
    la parte intera, poi i resti piu' grandi si prendono i passi avanzati."""
    n = round(totale / passo)
    if not voci or n <= 0:
        return {}
    tot = sum(voci.values()) or 1
    quote = {k: v / tot * n for k, v in voci.items()}
    base = {k: int(q) for k, q in quote.items()}
    resto = n - sum(base.values())
    for k in sorted(quote, key=lambda k: -(quote[k] - base[k]))[:resto]:
        base[k] += 1
    return {k: v * passo for k, v in base.items() if v}


# ------------------------------------------------------------------- report
def elabora(giorno, win, afk, mappa, classi, contesti=(), personali=(), win_host=None):
    b = clip_orario(blocchi_giorno(win))
    if not b:
        return None
    # La cornice - inizio, fine, pausa, ore in postazione - si misura sempre
    # sull'host: e' li' che Matteo e' fisicamente seduto. I dati della VM sono
    # molto piu' fitti (798 eventi contro 99, il 10/09) e la loro
    # frammentazione fa cadere sotto i 2 minuti i blocchi di inizio giornata:
    # misurando la cornice sui dati sostituiti, quel giorno cominciava alle
    # 08:33 invece che alle 08:25. La VM ridistribuisce le ore dentro la
    # giornata, non decide dove la giornata comincia.
    bh = clip_orario(blocchi_giorno(win_host)) if win_host is not None else []
    c = cornice(bh or b, afk)
    p0, p1 = c["pausa"]
    b = [x for x in b if not (x["inizio"] >= p0 and x["fine"] <= p1)]
    if not b:
        return None
    b = attribuisci(b, mappa, contesti, classi, personali)
    presenza = unisci([(dt(a["timestamp"]),
                        dt(a["timestamp"]) + timedelta(seconds=a["duration"]))
                       for a in afk if a["data"].get("status") == "not-afk" and a["duration"] > 0])

    righe, per_com, per_cat = [], collections.Counter(), collections.Counter()
    dedotto = collections.Counter()
    for x in b:
        t = x["titoli"].most_common(1)[0][0]
        attivo = sum((min(x["fine"], e) - max(x["inizio"], s)).total_seconds()
                     for s, e in presenza
                     if min(x["fine"], e) > max(x["inizio"], s))
        cat = categoria(classi, x["app"], t)
        righe.append({"inizio": x["inizio"].strftime("%H:%M"),
                      "fine": x["fine"].strftime("%H:%M"),
                      "durata": hm(x["durata"]),
                      "afk": hm(x["durata"] - timedelta(seconds=attivo))
                      if x["durata"].total_seconds() - attivo > 60 else "",
                      "app": x["app"], "titolo": t[:78],
                      "categoria": cat,
                      "commessa": x["commessa"],
                      "dedotta": x.get("dedotta", False)})
        per_cat[cat] += ore(x["durata"])
        voce = x["commessa"] or "Altro"
        per_com[voce] += ore(x["durata"])
        if x.get("dedotta"):
            dedotto[voce] += ore(x["durata"])
    voci, mute = ripartisci(b, c)
    prop = arrotonda(voci, ore(c["lavorate"]))
    # Quota dedotta dal contesto: e' la parte da rivedere per prima.
    quota = {}
    return {"data": giorno, "cornice": c, "righe": righe,
            "per_commessa": dict(per_com), "per_categoria": dict(per_cat),
            "proposta": prop, "senza_prove": mute}


def consuntivo(giorni, vm=False):
    """Il file che va in azienda: solo ore per commessa.

    Niente timeline e niente titoli di finestra. Nei fogli di lavoro compaiono
    'Hotel barcellona', la posta personale e le offerte di lavoro: sono
    indispensabili a Matteo per attribuire le ore, e non devono uscire di li'."""
    d0 = date.fromisoformat(giorni[0]["data"])
    somma = collections.Counter()
    for g in giorni:
        for k, v in g["proposta"].items():
            somma[k] += v
    L = [f"# Consuntivo ore — {MESI[d0.month - 1].capitalize()} {d0.year}", "",
         f"{len(giorni)} giorni lavorati · "
         f"{hm(timedelta(hours=sum(somma.values())))} totali", "",
         "| Commessa / voce | Ore | Giorni |", "|---|---:|---:|"]
    for k, v in somma.most_common():
        n = sum(1 for g in giorni if k in g["proposta"])
        L.append(f"| {k} | {hm(timedelta(hours=v))} | {n} |")
    L += [f"| **Totale** | **{hm(timedelta(hours=sum(somma.values())))}** | |", "",
          "## Dettaglio giornaliero", "", "| Giorno | In postazione | Ripartizione |",
          "|---|---:|---|"]
    for g in giorni:
        d = date.fromisoformat(g["data"])
        voci = " · ".join(f"{k} {hm(timedelta(hours=v))}"
                          for k, v in sorted(g["proposta"].items(), key=lambda x: -x[1]))
        L.append(f"| {GIORNI[d.weekday()]} {d:%d/%m} | {hm(g['cornice']['lavorate'])} | {voci} |")
    L += ["", "> Ore ricostruite dall'attivita' al PC, arrotondate alla mezz'ora."]
    # La nota cambia col mese: dichiarare "non attribuibile" un tempo che ora si
    # legge davvero sarebbe falso, ma dirlo sui mesi precedenti al watcher nella
    # VM lo sarebbe altrettanto.
    L += (["> Il tempo dentro la macchina virtuale e' letto dal watcher installato",
           "> al suo interno. Restano non attribuibili le sessioni di desktop remoto."]
          if vm else
          ["> Il tempo dentro macchine virtuali e sessioni di desktop remoto non e'",
           "> attribuibile a una commessa dai soli dati dell'host."])
    return "\n".join(L + [""])


def markdown(giorni, mappa):
    L = []
    if len(giorni) > 1:
        d0 = date.fromisoformat(giorni[0]["data"])
        tot = sum(ore(g["cornice"]["lavorate"]) for g in giorni)
        L += [f"# Log attività — {MESI[d0.month - 1].capitalize()} {d0.year}", "",
              f"{len(giorni)} giorni · {tot:.1f} h in postazione", ""]
        somma = collections.Counter()
        for g in giorni:
            for k, v in g["proposta"].items():
                somma[k] += v
        L += ["| Commessa / voce | Ore |", "|---|---:|"]
        for k, v in somma.most_common():
            L.append(f"| {k} | {hm(timedelta(hours=v))} |")
        L += [f"| **Totale** | **{hm(timedelta(hours=sum(somma.values())))}** |", "", "---", ""]

    for g in giorni:
        d = date.fromisoformat(g["data"])
        c = g["cornice"]
        p0, p1 = c["pausa"]
        if p1 > p0:
            nota = " *(dedotta: nessuna assenza registrata)*" if c["pausa_dedotta"] else ""
            riga_pausa = f" · pausa {p0:%H:%M}–{p1:%H:%M} ({hm(p1 - p0)}){nota}"
        else:
            riga_pausa = " · nessuna pausa (giornata non a cavallo del mezzogiorno)"
        L += [f"## {GIORNI[d.weekday()]} {d:%d/%m/%Y}", "",
              f"**{c['inizio']:%H:%M} → {c['fine']:%H:%M}**{riga_pausa} · "
              f"**{hm(c['lavorate'])} in postazione**", "",
              "### Ripartizione proposta", "", "| Commessa / voce | Ore |", "|---|---:|"]
        for k, v in sorted(g["proposta"].items(), key=lambda x: -x[1]):
            L.append(f"| {k} | {hm(timedelta(hours=v))} |")
        avviso = ("\n> Attenzione: il "
                  f"{round(g['senza_prove'] * 100)}% degli slot di 10 minuti non conteneva "
                  "nessuna prova di commessa ed e' stato assegnato per vicinanza."
                  if g["senza_prove"] >= 0.3 else "")
        L += [f"| **Totale** | **{hm(timedelta(hours=sum(g['proposta'].values())))}** |",
              avviso, "", "### Timeline", "",
              "| Ora | Durata | AFK | Programma | Titolo | Attribuito a |",
              "|---|---:|---:|---|---|---|"]
        for r in g["righe"]:
            com = r["commessa"] or "—"
            if r["dedotta"] and r["commessa"]:
                com += " ?"
            L.append(f"| {r['inizio']}–{r['fine']} | {r['durata']} | {r['afk'] or '–'} | "
                     f"`{r['app']}` | {r['titolo'].replace('|', '/')} | {com} |")
        L += ["", "### Totali per categoria ActivityWatch", "", "| Categoria | Tempo |", "|---|---:|"]
        for k, v in sorted(g["per_categoria"].items(), key=lambda x: -x[1]):
            L.append(f"| {k} | {hm(timedelta(hours=v))} |")
        L += ["", "> `?` = attribuzione dedotta dal contesto temporale, non dal titolo.",
              "> Correggila tu: e' il punto in cui i dati non bastano.", "", "---", ""]
    return "\n".join(L)


def main():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser()
    p.add_argument("--giorno")
    p.add_argument("--mese")
    p.add_argument("--da")
    p.add_argument("--a")
    p.add_argument("--out", required=True)
    p.add_argument("--config")
    p.add_argument("--rimappa", action="store_true")
    p.add_argument("--consuntivo", action="store_true",
                   help="solo ore per commessa, senza timeline ne titoli (file aziendale)")
    a = p.parse_args()

    if a.giorno:
        d0 = d1 = date.fromisoformat(a.giorno)
    elif a.mese:
        y, m = map(int, a.mese.split("-"))
        d0 = date(y, m, 1)
        d1 = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
    elif a.da:
        d0, d1 = date.fromisoformat(a.da), date.fromisoformat(a.a or a.da)
    else:
        p.error("indicare --giorno, --mese oppure --da/--a")

    cfg = json.load(open(a.config, encoding="utf-8")) if a.config else {}
    ignora = {AW.norm_code(c) for c in cfg.get("ignora", [])}
    host = AW.scopri_host()
    start = datetime.combine(d0, datetime.min.time()).astimezone()
    end = datetime.combine(d1 + timedelta(days=1), datetime.min.time()).astimezone()
    win, afk, fonte = AW.carica(host, start, end)
    print(f"[{fonte}] {len(win)} eventi finestra, {len(afk)} afk", file=sys.stderr)

    # Secondo livello: dove l'host dice "stavo guardando la VM", il dettaglio lo
    # da' il watcher che gira dentro la VM. L'AFK resta quello dell'host: e' li'
    # che Matteo e' fisicamente seduto, e l'input diretto alla finestra VMware
    # passa comunque dal sistema operativo dell'host.
    vm_usata = False
    win_host = win
    base = os.path.dirname(os.path.abspath(a.config)) if a.config else "."
    for db, rx, da, fino in compila_vm(cfg, base):
        ev = AW.carica_vm(db, start, end)
        win, sost = AW.innesta_vm(win, ev, rx, da, fino)
        vm_usata = vm_usata or sost > 0
        print(f"[vm] {os.path.basename(os.path.dirname(db))}: {len(ev)} eventi, "
              f"{hm(timedelta(seconds=sost))} di finestra VM sostituiti", file=sys.stderr)

    peso = AW.carica_mappa(host, end, ignora, a.rimappa)
    for code, cl in AW.costruisci_mappa(win, ignora).items():
        for k, v in cl.items():
            peso[code][k] = max(peso[code][k], v)
    mappa = {}
    for code, clienti in peso.items():
        if code in {AW.norm_code(k) for k in cfg.get("commesse", {})}:
            mappa[code] = cfg["commesse"][code]
        elif sum(clienti.values()) >= AW.MIN_EVIDENZA:
            best = max(clienti, key=clienti.get)
            # "Priv" da un titolo troncato da Windows (1 secondo di peso) non deve
            # vincere su "Privius" (3h reali) solo perche' e' piu' corto: la
            # famiglia si limita alle varianti con un minimo di ricorrenza vera.
            fam = [c for c in clienti if c.lower().startswith(best.lower()[:4]) and clienti[c] >= 60]
            mappa[code] = min(fam, key=len) if fam else best

    classi = carica_categorie()
    contesti = compila_contesti(cfg)
    personali = [re.compile(x, re.I) for x in cfg.get('personale', [])]
    per_g = collections.defaultdict(list)
    for e in win:
        per_g[dt(e["timestamp"]).date()].append(e)
    host_g = collections.defaultdict(list)
    for e in win_host:
        host_g[dt(e["timestamp"]).date()].append(e)
    afk_g = collections.defaultdict(list)
    for e in afk:
        afk_g[dt(e["timestamp"]).date()].append(e)

    giorni = []
    for g in sorted(per_g):
        r = elabora(g.isoformat(), per_g[g], afk_g[g], mappa, classi, contesti,
                    personali, host_g[g])
        if r:
            giorni.append(r)
    testo = consuntivo(giorni, vm_usata) if a.consuntivo else markdown(giorni, mappa)
    open(a.out, "w", encoding="utf-8").write(testo)
    print(f"scritto: {a.out}  ({len(giorni)} giorni)", file=sys.stderr)
    for g in giorni:
        print(f"  {g['data']}  {hm(g['cornice']['lavorate'])}  "
              + " · ".join(f"{k} {v}h" for k, v in sorted(g["proposta"].items(), key=lambda x: -x[1])),
              file=sys.stderr)


if __name__ == "__main__":
    main()
