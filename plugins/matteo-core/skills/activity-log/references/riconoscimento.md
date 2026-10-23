# Riconoscimento commesse e falsi positivi

Documenta *perché* i filtri sono fatti così. Ogni regola qui sotto nasce da un
caso misurato nei log reali di Matteo (bucket `aw-watcher-window_NB-MATTEO`,
storico dal 25/08/2025), non da un'ipotesi.

## Indice

- [Perché i dati grezzi mentono](#perché-i-dati-grezzi-mentono)
- [Forma di una commessa](#forma-di-una-commessa)
- [I falsi positivi misurati](#i-falsi-positivi-misurati)
- [Perché l'evidenza deve venire da un ambiente di sviluppo](#perché-levidenza-deve-venire-da-un-ambiente-di-sviluppo)
- [Aggiungere un software](#aggiungere-un-software)
- [Le due misure del tempo](#le-due-misure-del-tempo)

## Perché i dati grezzi mentono

Su 60 giorni di log, il tempo di finestra "attiva" totalizzava circa 1000 ore.
Di queste, **541,98 h erano `LockApp.exe`**: la schermata di blocco di Windows,
che ActivityWatch registra come finestra in primo piano mentre il PC è chiuso —
di notte, nei weekend, per giorni interi. Un singolo evento arrivava a coprire
oltre 8 ore. Altre 94,62 h erano finestre `unknown`, quasi tutte in eventi
singoli lunghissimi. Sommare le durate delle finestre così com'è sovrastima il
lavoro di un fattore 2–3: `LockApp.exe`/`unknown` sono nella lista `SISTEMA` e
vanno sempre scartate, senza eccezioni.

**Il modello attuale (`giornata.py`) non interseca con l'AFK.** Una prima
versione lo faceva, ma toglieva anche il tempo passato a leggere uno schema o
osservare un ciclo macchina senza toccare il mouse — proprio il collaudo che
doveva essere incluso. Il modello giusto è più semplice:

```
cornice stimata = ultima attività − prima attività − pausa pranzo
```

con due tagli che succhiano via il rumore prima ancora di arrivare a questo
calcolo:

- **Orario di lavoro 07:00–20:00**: qualunque blocco fuori fascia viene
  ritagliato (o scartato) prima di ogni altro calcolo. Regola dichiarata da
  Matteo esplicitamente, non dedotta dai dati.
- **Pausa dal bucket AFK, ma solo tra 1 e 3 ore.** Il bucket AFK riporta la
  durata *vera* di un'assenza, anche se dura giorni (weekend, ponte,
  malattia) — un'assenza di questo tipo, se iniziata a mezzogiorno, verrebbe
  scambiata per la pausa pranzo e sottrarrebbe l'intera durata, producendo un
  totale negativo. Sopra le 3 ore non si sottrae come pausa pranzo. Il
  motore non tronca automaticamente la giornata all'inizio dell'assenza:
  controllare gli eventi reali e le dichiarazioni per stabilire la fine. Se la
  giornata non attraversa il mezzogiorno (es. un pomeriggio iniziato alle
  15:47), non si deduce nessuna pausa di default.

Bug reali di questo tipo, trovati confrontando mesi interi: `2025-12-05` dava
-87h prima del tetto delle 3 ore (assenza di 3,8 giorni scambiata per pausa);
`2026-01-12` dava 13h46 prima del taglio orario (attività personale serale
alle 23:33 inclusa nel totale).

## Forma di una commessa

Codice di tre cifre (o quattro con zero iniziale) **adiacente a un nome
cliente**. I formati osservati:

| Formato | Esempio reale | Fonte |
|---|---|---|
| `Cliente+codice` | `Zilmet347 - TcXaeShell` | solution TwinCAT |
| `codice - Cliente - descrizione` | `0175 - Moretto Group s.p.a. - Isola puntatura` | titolo Sysmac |
| `codice-Cliente-Descrizione` | `349-CEB-PallettizzatoreScatole` | percorso Sysmac |
| `percorso\codice - Cliente` | `C:\OMRON\Data\VC\365 - Ergoal - Banco avvitatura` | percorso progetto |
| `codice_Cliente_Progetto` | `347_Zilmet_LineaAssemblaggioVasi0.1.cmtp` | progetto EasyBuilder |

`0349` e `349` sono la stessa commessa: il codice viene normalizzato a tre cifre.

Gli alias dello stesso codice vengono uniti. A parità di prefisso vince
l'etichetta più corta (`Hager` assorbe `HagerLineaMultiprocesso` e `HAGER`);
etichette non imparentate restano come alias e finiscono in `da_validare`
(es. `365` → `Ergoal`, con alias `BancoAvvitaturaRampeZepa`).

**Un'etichetta entra in gara per "più corta" solo se pesa almeno 60 secondi.**
Senza questo filtro, `350 → Privius` (3h25m reali) perdeva contro `350 → Priv`
— un titolo di TortoiseGit troncato da Windows, presente per **1 secondo** in
un mese intero, ma più corto e quindi vincente per la sola regola di
lunghezza. Bug trovato su ottobre 2025, corretto in `giornata.py`.

Una commessa entra in mappa solo con almeno **15 minuti cumulativi** di
evidenza. Sotto quella soglia si tratta quasi sempre di una coincidenza
numerica.

## I falsi positivi misurati

Cercare "tre cifre in un titolo" su 180 giorni produceva **147 commesse**, di cui
circa un centinaio inesistenti. Le classi, con il peso che avevano:

| Classe | Esempio nel titolo | Codici generati | Impatto |
|---|---|---|---|
| Indirizzi IP | `192.168.1.106 - Connessione Desktop remoto` | 192, 168, 106, 250 | **~112 h** |
| Versioni software | `EasyBuilder Pro V6.10.02.231` | 231, 284, 300, 510 | ~15 h |
| Modelli di prodotto | `Banco saldatura perni T300`, `PerniT450Cerniere` | 300, 450 | ~11 h |
| Pagine HMI | `[105 - Setup Sistema]`, `[111 - Setup Assi]` | 105, 111, 113–115 | ~2 h |
| Variabili PLC | `AsseZ`, `Preset encoder`, `AllarmiBanco` | 100, 102, 118, 121 | minore |
| Codici HTTP | `404 Not Found`, `403 Forbidden` | 401, 403, 404 | minore |
| Shopping e news | `600 - Nero 177 cm EAT6ME53K0`, `512 GB di archiviazione` | 512, 600, 601 | minore |
| Nomi file | `Indirizzi.txt`, `QG.pdf` | 169, 004 | minore |
| Grandezze elettriche/meccaniche | `Filtro antidisturbo di rete 250 V 16 A` | 250 | trovato in seguito, minore |
| Sigle prodotto maiuscole | `Schaffner FN2090-16-06` | — | trovato in seguito, minore |

Un caso vale da solo: `300 → "miliardi di anni luce"`, da un articolo letto nel
browser. Le due righe di grandezze/sigle sono state trovate mesi dopo le
prime 147→24, cercando un ricambio online (`Filtro antidisturbo di rete 250 V
16 A` generava una finta commessa "250"): il rumore non è mai finito di
elencare, cresce ogni volta che Matteo cerca qualcosa online con un numero
vicino a un'unità di misura o a una sigla di prodotto.

Nota sull'ordine delle sostituzioni: il rumore va tolto **prima** di cercare i
codici. Un titolo come
`EasyBuilder Pro V6.10.01.510 : 354_AffilaturaCastellana_IncisoreLame.cmtp - [105 - Setup Sistema]`
contiene contemporaneamente un numero di build (510), il codice vero (354) e una
pagina HMI (105). Prendere "il primo numero che sembra un codice" darebbe la
risposta sbagliata.

### Il caso `T450` / `Zilmet347`

I modelli prodotto vanno rimossi, ma la regola ingenua `[Tt]\d{3,4}` cancella
anche `Zilme**t**347` — cioè la commessa con più ore in assoluto (129 h).

La distinzione è la maiuscola: in `PerniT450` la `T` è isolata o in confine
CamelCase, in `Zilmet347` la `t` è minuscola dentro la parola. Da qui
`(?:(?<![A-Za-zÀ-ÿ0-9])[Tt]|(?<=[a-zà-ÿ])T)\d{3,4}`.

Questo caso è coperto da `test_estrazione.py`. Non modificare quella regex senza
rilanciare i test.

## Perché l'evidenza deve venire da un ambiente di sviluppo

Il filtro che da solo elimina la maggior parte del rumore: **la mappa
codice→cliente si costruisce solo da titoli di app PLC/HMI o da titoli che
contengono un percorso su disco.** I titoli del browser sono esclusi.

È lì che nascono `404 Not Found`, `600 Nero 177 cm`, `Menù di oggi`: hanno
esattamente la forma di una commessa (numero + parole) ma non lo sono, e nessun
filtro lessicale li prende tutti. La provenienza sì.

Con questo filtro più la soglia dei 15 minuti, le 147 commesse diventano **24**,
tutte con cliente riconoscibile.

L'attribuzione dei singoli eventi passa poi *solo* per codici già presenti in
mappa. Un evento del browser non può quindi inventare una commessa nuova.

## Aggiungere un software

`CATEGORIE` dentro `scripts/aw_report.py` contiene solo `plc` e `hmi` — nomi
eseguibile in minuscolo. Serve a un'unica cosa: distinguere un'evidenza forte
(codice letto dentro un ambiente di sviluppo) da una debole (stesso numero
letto nel browser), e a riconoscere quando un blocco senza codice è comunque
"un ambiente di sviluppo aperto" (regola 3 di attribuzione in `SKILL.md`).

Le altre categorie che compaiono nella scaletta (remoto, AI, documentazione,
web...) **non vengono più da qui**: sono lette a runtime dalle classi che
Matteo ha definito nella UI di ActivityWatch (`categoria()` in `giornata.py`,
che legge `settings.json`). Un tempo `CATEGORIE` conteneva anche quelle come
lista parallela — è stato codice morto per un po' (nessuno le leggeva più dopo
il passaggio al modello a mezz'ore) ed è stato rimosso quando se n'è accorto
in sessione: se ricompaiono qui liste come `remoto`/`ai`/`comunicazione`, è un
segno di regressione, non una funzionalità da ripristinare.

Attenzione al nome reale del processo, che spesso non è il nome commerciale:
TwinCAT compare come `TcXaeShell.exe`, non `TwinCAT.exe`. Per scoprirlo:

```bash
curl -s "http://localhost:5600/api/0/buckets/aw-watcher-window_NB-MATTEO/events?limit=200" | python -c "import json,sys,collections; print(collections.Counter(e['data']['app'] for e in json.load(sys.stdin)))"
```

Se un'app di sviluppo non è in `plc`/`hmi`, le sue ore non fanno da ancora per
nessuna commessa: è la causa più probabile di una giornata con molte ore in
postazione e poche attribuite.

## Le due misure del tempo

Non sono la stessa cosa e vanno tenute distinte quando si risponde a Matteo:

- **Ore in postazione** — quello che produce `cornice()`: ultima attività meno
  prima attività meno pausa, dentro la fascia 07:00–20:00. È una cornice stimata,
  non una misura continua del lavoro al PC; controllare copertura e vuoti
  nei giorni anomali. Le dichiarazioni su lavoro senza PC, pause e viaggio
  si trattano secondo [rendicontazione.md](rendicontazione.md).
- **Ripartizione per commessa** — quello che produce `ripartisci()`: una
  proposta costruita votando ogni mezz'ora, non un dato misurato. Calibrata
  contro giornate ricostruite a mano da Matteo, sbaglia tipicamente di mezz'ora
  per voce e molto di più quando gran parte della giornata passa da finestre
  mute (VM, Desktop Remoto, `claude.exe`) senza nulla vicino che ancori.

C'è una terza misura, distinta dalle prime due, che riguarda solo il tempo
**senza commessa**: il pool "grezzo" (nessuna prova, misurato da
`analisi_altro.py`, limitato al 01/10/2025–06/08/2026 e senza VM) è quasi il doppio di quanto appare come "Altro" nei
consuntivi mensili, perché la regola di vicinanza in `ripartisci()` assegna
metà di quel tempo a una commessa vicina anche senza prova diretta. Vedi
`SKILL.md`, sezione "Analisi del tempo non attribuito".
