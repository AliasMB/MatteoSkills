#!/usr/bin/env python3
"""
aw_report.py - Acquisizione dati ActivityWatch e riconoscimento delle commesse.

Libreria usata da giornata.py: non si esegue da sola. Qui stanno la lettura dei
bucket e le regole che distinguono un codice commessa da un indirizzo IP, un
numero di build o una pagina HMI. I casi limite sono coperti da
test_estrazione.py: se tocchi le espressioni regolari, rilancia i test.

SOLA LETTURA. Non scrive mai sul database ne' sui log di ActivityWatch:
l'API viene interrogata solo in GET, il fallback SQLite usa mode=ro&immutable=1.

"""

import json
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timedelta, date, timezone

API = "http://localhost:5600/api/0"
DB = r"C:\Users\Matteo\AppData\Local\activitywatch\activitywatch\aw-server\peewee-sqlite.v2.db"

# ------------------------------------------------- ambienti di sviluppo
# Serve solo a stabilire QUANTO E' FORTE un'evidenza: un codice commessa letto
# dentro Sysmac o TwinCAT vale, lo stesso numero letto nel browser no. Le
# categorie mostrate nel report sono invece quelle definite da Matteo nella UI
# di ActivityWatch, lette a runtime da giornata.py — non duplicarle qui.
CATEGORIE = {
    "plc": ["sysmacstudio.exe", "tcxaeshell.exe", "twincat.exe", "cx-p.exe",
            "cx-programmer.exe", "g9spconfigurator.exe", "rslogix.exe",
            "studio 5000", "siemens.automation.portal.exe", "nxstudio.exe",
            "network configurator.exe", "cx-designer.exe"],
    "hmi": ["easybuilder pro.exe", "nb-designer.exe", "iv-navigator.exe",
            "wincc.exe", "easybuilder8000.exe"],
}
# Mai lavoro: schermata di blocco, menu Start, shell, finestre non identificate.
SISTEMA = {"lockapp.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
           "unknown", "dwm.exe", "searchhost.exe", "textinputhost.exe",
           "applicationframehost.exe", "systemsettings.exe", "logonui.exe",
           "widgets.exe", "searchapp.exe", ""}

APP2CAT = {a: c for c, apps in CATEGORIE.items() for a in apps}
MIN_EVIDENZA = 900          # 15 min cumulativi: soglia per entrare nella mappa
SVILUPPO = {"plc", "hmi"}          # ambienti che identificano una commessa

# --------------------------------------------------- pulizia titoli / rumore
# Ordine importante: si toglie il rumore PRIMA di cercare i codici commessa,
# altrimenti IP e numeri di build generano commesse fantasma.
RUMORE = [
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), " "),   # IP: 192.168.1.106
    (re.compile(r"[vV]?\d+\.\d+(?:\.\d+)+"), " "),                   # build: V6.10.02.231
    (re.compile(r"\[[^\[\]]{0,60}?\]"), " "),                        # pagina HMI: [105 - Setup]
    (re.compile(r"\[[^\[\]]{0,60}$"), " "),                          # ...anche se il titolo e' troncato
    # Modelli di prodotto T300 / PerniT450Cerniere. La T dev'essere isolata o in
    # confine CamelCase: cosi' "Zilmet347" (t minuscola dentro la parola) e'
    # salvo, mentre "PerniT450" viene tolto.
    (re.compile(r"(?:(?<![A-Za-zÀ-ÿ0-9])[Tt]|(?<=[a-zà-ÿ])T)\d{3,4}"), " "),
    # Grandezze elettriche e meccaniche: "Filtro di rete 250 V 16 A" non e' la
    # commessa 250, e' una tensione. Capita spesso cercando ricambi online.
    (re.compile(r"(?i)\b\d+[.,]?\d*\s?(?:V|A|mA|kW|kV|W|Hz|kHz|mm|cm|bar|kg|Nm|rpm|VAC|VDC)\b"), " "),
    # Sigle di prodotto tipo FN2090-16-06: maiuscole e almeno 4 cifre, cosi'
    # "Zilmet347" (minuscole, 3 cifre) non viene toccato.
    (re.compile(r"\b[A-Z]{2,4}\d{4,}[-\w]*"), " "),
    (re.compile(r"\b(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b"), " "),  # date
    (re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"), " "),              # orari
]

# Parole che non sono mai un nome cliente.
NON_CLIENTI = {
    "cpu", "plc", "hmi", "io", "setup", "sistema", "main", "rev", "ver", "version",
    "page", "pagina", "banco", "linea", "macchina", "progetto", "manuale", "copy",
    "backup", "new", "test", "prova", "documenti", "google", "chrome", "windows",
    "microsoft", "office", "safety", "program", "task", "global", "var", "config",
    "online", "offline", "build", "error", "warning", "run", "stop", "start",
    "download", "upload", "cartella", "file", "nuovo", "senza", "untitled",
}

# code-first:  "365 - Ergoal - ...", "349-CEB-...", "0175 - Moretto Group s.p.a. - ..."
P_CODE_FIRST = re.compile(
    r"(?<![A-Za-z\d])(0\d{3}|\d{3})(?!\d)\s*[-_ ]\s*"
    r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9&'.\- ]{1,30}?)(?=\s*[-_|\\/\[\]:,]|\s\s|$)")
# code-last:   "Zilmet347", "AffilaturaCastellana354"
P_CODE_LAST = re.compile(
    r"(?<![A-Za-zÀ-ÿ\d])([A-ZÀ-Ý][A-Za-zÀ-ÿ]{2,30}?)(0\d{3}|\d{3})(?![\d])")
# codice nudo: "347" senza cliente accanto -> utilizzabile solo con mappa gia' costruita
P_CODE_SOLO = re.compile(r"(?<![A-Za-z\d.])(0\d{3}|\d{3})(?![\d.])")


def pulisci(titolo):
    t = titolo or ""
    for rx, sub in RUMORE:
        t = rx.sub(sub, t)
    return t


def norm_code(c):
    """0349 e 349 sono la stessa commessa."""
    return c.lstrip("0").zfill(3)


def estrai_candidati(titolo):
    """Ritorna [(codice, cliente)] con evidenza forte (codice adiacente a cliente)."""
    t = pulisci(titolo)
    out = []
    for m in P_CODE_FIRST.finditer(t):
        cli = m.group(2).strip(" -_.")
        if cli.lower() not in NON_CLIENTI and not cli.isdigit() and len(cli) >= 3:
            out.append((norm_code(m.group(1)), cli))
    for m in P_CODE_LAST.finditer(t):
        cli = m.group(1).strip()
        if cli.lower() not in NON_CLIENTI and len(cli) >= 3:
            out.append((norm_code(m.group(2)), cli))
    return out


# ------------------------------------------------------------- acquisizione
def _fetch_api(bucket, start, end):
    # Il '+' del fuso orario va percent-encoded, altrimenti aw-server lo legge
    # come spazio e risponde 500.
    qs = urllib.parse.urlencode({"start": start.isoformat(), "end": end.isoformat(),
                                 "limit": -1})
    with urllib.request.urlopen(f"{API}/buckets/{bucket}/events?{qs}", timeout=120) as r:
        return json.load(r)


def _fetch_db(bucket, start, end, db=None):
    """Fallback se aw-server e' spento. Connessione in sola lettura.

    'db' serve anche per leggere la copia del database di una macchina
    virtuale, che e' un file e basta: li' non c'e' nessun aw-server acceso."""
    con = sqlite3.connect(f"file:{db or DB}?mode=ro&immutable=1", uri=True)
    try:
        key = con.execute("select key from bucketmodel where id=?", (bucket,)).fetchone()
        if not key:
            return []
        # Il DB salva 'YYYY-MM-DD HH:MM:SS.ffffff+00:00' in UTC: il confronto e'
        # testuale, quindi i limiti vanno normalizzati allo stesso formato.
        fmt = lambda d: d.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        rows = con.execute(
            "select timestamp, duration, datastr from eventmodel "
            "where bucket_id=? and timestamp>=? and timestamp<? order by timestamp",
            (key[0], fmt(start), fmt(end))).fetchall()
        return [{"timestamp": r[0], "duration": float(r[1]), "data": json.loads(r[2])}
                for r in rows]
    finally:
        con.close()


def carica(host, start, end):
    win, afk = f"aw-watcher-window_{host}", f"aw-watcher-afk_{host}"
    try:
        return _fetch_api(win, start, end), _fetch_api(afk, start, end), "api"
    except (urllib.error.URLError, OSError):
        return _fetch_db(win, start, end), _fetch_db(afk, start, end), "sqlite (sola lettura)"


def scopri_host():
    try:
        with urllib.request.urlopen(f"{API}/buckets/", timeout=30) as r:
            for b in json.load(r):
                if b.startswith("aw-watcher-window_"):
                    return b.split("_", 1)[1]
    except (urllib.error.URLError, OSError):
        con = sqlite3.connect(f"file:{DB}?mode=ro&immutable=1", uri=True)
        try:
            row = con.execute("select id from bucketmodel where id like 'aw-watcher-window_%'").fetchone()
            if row:
                return row[0].split("_", 1)[1]
        finally:
            con.close()
    raise SystemExit("Nessun bucket aw-watcher-window trovato.")


# ------------------------------------------------- seconda sorgente: la VM
def carica_vm(db, start, end):
    """Eventi finestra da una copia del database di una macchina virtuale.

    ActivityWatch gira anche dentro la VM, ma il suo database sta li' dentro:
    Matteo ne copia il file a mano una volta al mese. Qui si legge quella
    copia, sempre in sola lettura come tutto il resto."""
    con = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
    try:
        row = con.execute("select id from bucketmodel "
                          "where id like 'aw-watcher-window_%'").fetchone()
    finally:
        con.close()
    return _fetch_db(row[0], start, end, db) if row else []


def _ts(e):
    return datetime.fromisoformat(str(e["timestamp"]).replace("Z", "+00:00")).astimezone()


def innesta_vm(win, vm, rx, da=None, a=None, etichetta="[VM] "):
    """Sostituisce il tempo sulla finestra della VM con quello che la VM ha
    registrato al proprio interno.

    Gerarchia: prima l'host, poi la VM. L'host dice QUANDO Matteo stava
    guardando la macchina virtuale, la VM dice COSA c'era dentro. Le due
    sorgenti non si sommano mai: il watcher del guest continua a registrare
    anche mentre la finestra VMware non e' in primo piano sull'host, perche'
    dentro il guest una finestra e' sempre attiva. Misurato il 25/08: l'host
    vede 6h58 sulla finestra VM, la VM ne registra 9h34. Sommarle, o fidarsi
    della VM da sola, significherebbe contare ore in cui Matteo guardava
    altro.

    Dove la VM non ha dati per un intervallo - VM sospesa, watcher fermo,
    periodo precedente alla sua installazione - l'evento dell'host resta
    com'e' e se ne occupa la regola di contesto in commesse.json, che e' il
    terzo livello. Il 14/09 e' il caso reale: l'host vede 2h19 di finestra VM
    e la VM ne registra 33m.

    I titoli sostituiti sono marcati con 'etichetta' perche' nel foglio di
    lavoro si veda da dove arrivano: dentro la VM girano anche explorer.exe e
    claude.exe, che altrimenti sarebbero indistinguibili da quelli dell'host.
    Il marcatore ha la forma [..] e viene tolto da pulisci() prima che si
    cerchino i codici commessa, quindi non interferisce col riconoscimento.
    """
    if not vm:
        return win, 0.0
    fin = sorted((_ts(e), _ts(e) + timedelta(seconds=e["duration"]), e["data"])
                 for e in vm if e["duration"] > 0)
    out, j, sostituito = [], 0, 0.0
    for e in sorted(win, key=_ts):
        s = _ts(e)
        f = s + timedelta(seconds=e["duration"])
        d = e["data"] or {}
        g = s.date()
        if not rx.search(f"{d.get('app', '')} {d.get('title', '')}") \
                or (da and g < da) or (a and g > a):
            out.append(e)
            continue
        # Gli eventi dell'host arrivano in ordine e non si sovrappongono, quindi
        # il puntatore sulla VM avanza una volta sola su tutta la giornata.
        while j < len(fin) and fin[j][1] <= s:
            j += 1
        dentro, coperto = [], []
        for vs, vf, vd in fin[j:]:
            if vs >= f:
                break
            # Schermata di blocco, avvio, finestra non identificata: la VM non
            # sta dicendo cosa faceva Matteo, e a valle questi eventi vengono
            # scartati. Trattarli come sostituzione accorcerebbe la giornata -
            # il 10/09 la VM in avvio alle 08:25 spostava l'inizio alle 08:33 -
            # quindi restano un buco e se li riprende l'host.
            if (vd.get("app") or "").lower() in SISTEMA:
                continue
            lo, hi = max(vs, s), min(vf, f)
            if hi > lo:
                # Il titolo dell'host resta in coda a quello della VM. Serve
                # alle finestre mute: dentro la VM girano claude.exe, explorer
                # e il browser, che non dicono niente da soli. Senza questa
                # coda perderebbero anche cio' che l'host sapeva - "questa e'
                # la VM di SMEG" - e il 31/08 i 72 minuti di claude.exe
                # dentro la VM uscivano dalla commessa per finire in Altro.
                # La VM raffina quello che l'host sa, non lo cancella.
                dentro.append({"timestamp": lo.isoformat(),
                               "duration": (hi - lo).total_seconds(),
                               "data": dict(vd, title=f"{etichetta}{vd.get('title') or ''}"
                                                       f" · {d.get('title') or ''}")})
                if coperto and lo <= coperto[-1][1]:
                    coperto[-1][1] = max(coperto[-1][1], hi)
                else:
                    coperto.append([lo, hi])
        if not dentro:
            out.append(e)
            continue
        # I buchi tornano all'host. La VM copre spesso solo una parte
        # dell'intervallo - si avvia, si sospende, il watcher parte in ritardo -
        # e lasciare scoperto quel tempo accorcerebbe la giornata: senza questo
        # recupero il 10/09 passava da 7h31 a 7h17 di ore in postazione. La
        # cornice della giornata la detta l'host e non deve mai cambiare.
        t = s
        for lo, hi in coperto:
            if lo > t:
                dentro.append({"timestamp": t.isoformat(),
                               "duration": (lo - t).total_seconds(), "data": d})
            t = max(t, hi)
        if t < f:
            dentro.append({"timestamp": t.isoformat(),
                           "duration": (f - t).total_seconds(), "data": d})
        out.extend(dentro)
        sostituito += sum(((hi - lo) for lo, hi in coperto), timedelta()).total_seconds()
    return sorted(out, key=_ts), sostituito


# --------------------------------------------------------------------- core
# Un nome cliente non e' un file, ne' il nome di un programma.
RX_FILE = re.compile(r"\.(pdf|txt|xlsx?|docx?|pptx?|cmtp|smc2|tsproj|sln|jpg|png|zip|csv|json|log|bak)\b", re.I)
NON_CLIENTI_RX = re.compile(
    r"(?i)^(google chrome|cerca con google|esplora file|mozilla thunderbird|anydesk|"
    r"youtube|notepad\+\+|setup [a-z]+|preset [a-z]+|messaggi[a-z]*|allarmi[a-z ]*|"
    r"asse[xyz]|out|in|mess|manuale[a-z ]*|dichirazione|distinta[a-z ]*|variabili|"
    r"info|indirizzi|address|note tecniche|e altre? \d|.* pagine?|euro.*|gb di .*|"
    r"pin ddr\d.*|.* cm [a-z0-9]+|miliardi.*|authorization required|unauthorized|"
    r"forbidden|not found|page not found|resource not found|precompilato.*|"
    r"men[uù] di oggi|max|series|manual|hours|voti|bmr|nero \d.*)$")


def cliente_plausibile(nome):
    return not RX_FILE.search(nome) and not NON_CLIENTI_RX.match(nome.strip())


def costruisci_mappa(eventi, ignora):
    """Peso (codice -> cliente -> secondi) dalle sole evidenze forti.

    Evidenza forte = il codice compare accanto al cliente dentro un ambiente di
    sviluppo PLC/HMI oppure dentro un percorso su disco. I titoli del browser
    sono esclusi: e' li' che nascono '404 Not Found', '600 Nero 177 cm' e simili,
    che hanno la stessa forma di una commessa ma non lo sono.
    """
    peso = defaultdict(lambda: defaultdict(float))
    for e in eventi:
        app = (e["data"].get("app") or "").lower()
        titolo = e["data"].get("title", "") or ""
        forte = APP2CAT.get(app) in SVILUPPO or "\\" in titolo or "/" in titolo
        if app in SISTEMA or not forte:
            continue
        for code, cli in estrai_candidati(titolo):
            if code not in ignora and cliente_plausibile(cli):
                peso[code][cli] += e["duration"]
    return peso




CACHE = __file__.replace("aw_report.py", ".mappa_cache.json")
GIORNI_MAPPA = 180


def carica_mappa(host, fine, ignora, forza):
    """Mappa codice->cliente su 180 giorni, in cache: rileggere 125k eventi a
    ogni report giornaliero sarebbe lento e inutile."""
    try:
        c = json.load(open(CACHE, encoding="utf-8"))
        fresca = (datetime.now() - datetime.fromisoformat(c["aggiornata"])).days < 7
        if fresca and not forza:
            return defaultdict(lambda: defaultdict(float),
                               {k: defaultdict(float, v) for k, v in c["peso"].items()})
    except (OSError, ValueError, KeyError):
        pass
    print("[mappa commesse: ricostruzione su 180 giorni...]", file=sys.stderr)
    win, _, _ = carica(host, fine - timedelta(days=GIORNI_MAPPA), fine)
    peso = costruisci_mappa(win, ignora)
    try:
        json.dump({"aggiornata": datetime.now().isoformat(), "peso": peso},
                  open(CACHE, "w", encoding="utf-8"))
    except OSError:
        pass
    return peso
