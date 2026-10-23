#!/usr/bin/env python3
"""Analisi della categoria 'Altro': quanto pesa al giorno, i picchi, e quanta
parte e' riconoscibile come personale (marcatori espliciti: WhatsApp, YouTube,
Gmail privato, shopping, offerte di lavoro, categorie Media/IM di ActivityWatch)
contro quanta e' solo 'senza aggancio a una commessa' - che non e' la stessa cosa
di aver perso tempo, e va tenuta distinta invece di sommarla per intuito."""
import sys, collections
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import giornata as G, aw_report as AW
from datetime import datetime, timedelta, date

CFG_PATH = r"C:\Users\Matteo\Documents\AI_Projects\Varie\ActivityLog\commesse.json"
import json
cfg = json.load(open(CFG_PATH, encoding="utf-8"))
ignora = {AW.norm_code(c) for c in cfg.get("ignora", [])}
contesti = G.compila_contesti(cfg)
personali = [__import__("re").compile(x, __import__("re").I) for x in cfg.get("personale", [])]
classi = G.carica_categorie()

host = AW.scopri_host()
d0, d1 = date(2025, 10, 1), date(2026, 8, 6)
start = datetime.combine(d0, datetime.min.time()).astimezone()
end = datetime.combine(d1 + timedelta(days=1), datetime.min.time()).astimezone()
win, afk, fonte = AW.carica(host, start, end)
print(f"[{fonte}] {len(win)} eventi, periodo {d0}..{d1}", file=sys.stderr)

peso = AW.carica_mappa(host, end, ignora, False)
for code, cl in AW.costruisci_mappa(win, ignora).items():
    for k, v in cl.items():
        peso[code][k] = max(peso[code][k], v)
mappa = {}
for code, clienti in peso.items():
    if sum(clienti.values()) >= AW.MIN_EVIDENZA:
        best = max(clienti, key=clienti.get)
        fam = [c for c in clienti if c.lower().startswith(best.lower()[:4]) and clienti[c] >= 60]
        mappa[code] = min(fam, key=len) if fam else best

per_g = collections.defaultdict(list)
for e in win:
    per_g[G.dt(e["timestamp"]).date()].append(e)
afk_g = collections.defaultdict(list)
for e in afk:
    afk_g[G.dt(e["timestamp"]).date()].append(e)

# --- raccolta: per ogni blocco NON ancorato a commessa/ricerca, classifica
giorni = {}          # data -> {"personale":sec, "non_attribuito":sec, "app_pers":Counter, "app_non":Counter}
tot_altro_ripartito = 0.0   # per confronto col numero gia' pubblicato nei consuntivi
titoli_chrome_non_attr = collections.Counter()

for g in sorted(per_g):
    b = G.clip_orario(G.blocchi_giorno(per_g[g]))
    if not b:
        continue
    c = G.cornice(b, afk_g[g])
    p0, p1 = c["pausa"]
    b = [x for x in b if not (x["inizio"] >= p0 and x["fine"] <= p1)]
    if not b:
        continue
    b = G.attribuisci(b, mappa, contesti, classi, personali)

    dd = {"personale": 0.0, "non_attribuito": 0.0,
          "app_pers": collections.Counter(), "app_non": collections.Counter()}
    for x in b:
        if x.get("ancora") or x.get("ricerca"):
            continue
        sec = x["durata"].total_seconds()
        t = x["titoli"].most_common(1)[0][0]
        cat = G.categoria(classi, x["app"], t)
        if x.get("personale") or G.e_personale(cat, x["app"], t, personali):
            dd["personale"] += sec
            dd["app_pers"][x["app"]] += sec
        else:
            dd["non_attribuito"] += sec
            dd["app_non"][x["app"]] += sec
            if x["app"].lower() == "chrome.exe":
                titoli_chrome_non_attr[t] += sec
    giorni[g] = dd

    # ripartisci() gia' restituisce ore (non secondi): niente doppia divisione
    voci, _ = G.ripartisci(b, c)
    tot_altro_ripartito += voci.get("Altro", 0.0)

# ---------------------------------------------------------------- riepilogo
n = len(giorni)
tot_pers = sum(d["personale"] for d in giorni.values()) / 3600
tot_non = sum(d["non_attribuito"] for d in giorni.values()) / 3600
tot_pool = tot_pers + tot_non

print(f"\n=== POOL 'Altro' (blocchi senza commessa/ricerca), {n} giorni ===")
print(f"  personale (marcatori espliciti): {tot_pers:7.1f} h   media/giorno: {tot_pers/n:.2f} h")
print(f"  non attribuito (senza aggancio): {tot_non:7.1f} h   media/giorno: {tot_non/n:.2f} h")
print(f"  totale pool:                     {tot_pool:7.1f} h   media/giorno: {tot_pool/n:.2f} h")
print(f"\n  quota personale sul pool: {100*tot_pers/tot_pool:.1f}%")
print(f"  (confronto: 'Altro' nei consuntivi mensili gia' pubblicati ~= {tot_altro_ripartito:.1f} h"
      f" - leggermente diverso perche' li' i vuoti si accodano alla mezz'ora vicina)")

print(f"\n=== TOP 15 GIORNI DI PICCO (pool 'Altro' totale) ===")
rank = sorted(giorni.items(), key=lambda kv: -(kv[1]["personale"]+kv[1]["non_attribuito"]))[:15]
for g, d in rank:
    tot = (d["personale"]+d["non_attribuito"])/3600
    pers = d["personale"]/3600
    print(f"  {g}  {tot:5.2f}h totali  (personale {pers:4.2f}h = {100*pers/tot:.0f}%)")

print(f"\n=== APP CHE COMPONGONO LA PARTE 'PERSONALE' (top 12, ore totali periodo) ===")
appc = collections.Counter()
for d in giorni.values(): appc.update(d["app_pers"])
for a, s in appc.most_common(12): print(f"  {s/3600:6.1f}h  {a}")

print(f"\n=== APP CHE COMPONGONO LA PARTE 'NON ATTRIBUITO' (top 12) ===")
appc = collections.Counter()
for d in giorni.values(): appc.update(d["app_non"])
for a, s in appc.most_common(12): print(f"  {s/3600:6.1f}h  {a}")

print(f"\n=== CAMPIONE: titoli Chrome dentro 'non attribuito' (top 25 per tempo) ===")
print("  (nessun automatismo li classifica: guardali tu, e' l'unico modo onesto")
print("   di stimare quanto di questo 91% e' lavoro senza aggancio vs. altro)")
for t, s in titoli_chrome_non_attr.most_common(25):
    print(f"  {s/3600:5.2f}h  {t[:75]}")

print(f"\n=== DISTRIBUZIONE MENSILE ===")
mesi = collections.defaultdict(lambda: [0.0, 0.0])
for g, d in giorni.items():
    k = f"{g.year}-{g.month:02d}"
    mesi[k][0] += d["personale"]/3600
    mesi[k][1] += d["non_attribuito"]/3600
for k in sorted(mesi):
    p, nn = mesi[k]
    print(f"  {k}  personale {p:5.1f}h  non_attrib {nn:5.1f}h  tot {p+nn:5.1f}h")
