---
name: activity-log
description: "Ricostruisce le ore per commessa dai dati ActivityWatch (foglio giornaliero, consuntivo mensile). Usa quando Matteo chiede ore, consuntivo, timesheet, rendiconto, \"cosa ho fatto ieri\" o nomina ActivityWatch."
---

# Ore per commessa da ActivityWatch

Lo scopo è arrivare a dire, a fine giornata, **quante ore sono andate su ogni
commessa**, ripartendo il totale effettivo della giornata. Le 8 ore sono
un riferimento, non un totale da imporre.

Per dichiarazioni correttive, trasferte/viaggio, lavoro senza PC e analisi
delle chat o del personale, leggere prima
[references/rendicontazione.md](references/rendicontazione.md). Queste
revisioni si documentano nel report: non sono automatismi degli script.

## Il modello

Non si sommano i tempi delle finestre: si ricostruisce la giornata e la si
divide.

```
cornice stimata = ultima attività − prima attività − pausa pranzo
```

La pausa si legge dal **bucket AFK**, non dai buchi tra le finestre. Il 04/08 la
finestra di Desktop Remoto è rimasta in primo piano per tutta la pausa
simulando lavoro, mentre l'AFK segnava correttamente 89 minuti di assenza.
Nel conteggio vale la durata effettiva della pausa pranzo, quando
identificabile nei dati o confermata da Matteo: non si sostituisce con
1h30 di default. Se mancano dati e conferma, in sede il default è 1h30;
si deduce solo quando la cornice contiene
12:30–14:00. La pausa dichiarata per date specifiche sostituisce la deduzione
(trasferte SMEG: circa 1h), senza ridurre automaticamente un
AFK misurato più lungo. Un AFK misura un'assenza, non ne prova il motivo; i conflitti si chiariscono con Matteo.

Il tempo **non** viene intersecato con l'AFK. Leggere uno schema o guardare un
ciclo macchina è lavoro anche senza toccare il mouse; intersecare toglieva circa
un'ora e mezza al giorno e faceva sparire proprio il collaudo.

Verificato contro due giornate ricostruite a mano da Matteo: 24/06 → 8h05,
04/08 → 7h54.

## Due sorgenti, in gerarchia

Dal **24/08/2026** ActivityWatch gira anche dentro la macchina virtuale
`SiemensPC`, quella con TIA Portal. Le sorgenti si leggono in ordine, e non si
sommano mai:

1. **Macchina fisica** (`NB-MATTEO`). Detta la cornice della giornata — inizio,
   fine, pausa, ore in postazione — e dice *quando* Matteo stava guardando la
   VM. Questo livello non si tocca: è lì che è fisicamente seduto, ed è da lì
   che arriva l'AFK.
2. **VM** (`SiemensPC`). Solo dentro gli intervalli in cui l'host dice "finestra
   VMware in primo piano", e dice *cosa* c'era dentro.
3. **Contesto** di `commesse.json`. Dove la VM non ha dati — sospesa, watcher
   fermo, o periodo precedente alla sua installazione.

**Non sommare host e VM, e non fidarsi della VM da sola.** Dentro il guest una
finestra è sempre attiva, quindi il watcher della VM continua a registrare anche
mentre Matteo sta guardando altro sull'host: il 25/08 l'host vede 6h58 di
finestra VM e la VM ne registra 9h34. Il 14/09 vale il contrario (host 2h19, VM
33m) ed è il motivo per cui il livello 3 non va rimosso.

Prima del 24/08/2026 esiste solo la macchina fisica e il ragionamento resta
quello di sempre. I consuntivi già salvati si conservano. Il precedente innesto VM fu verificato
rigenerando giugno e agosto; il nuovo passo a 10 minuti può cambiare una
rigenerazione, quindi non sovrascrivere mesi storici senza richiesta.

La cornice non certifica presenza continua al PC: nei giorni con vuoti
lunghi controllare gli eventi grezzi e distinguere lavoro dichiarato,
assenza e copertura mancante.

## Come si esegue

```powershell
python "${CLAUDE_SKILL_DIR}\scripts\giornata.py" --giorno 2026-06-24 --config "$env:USERPROFILE\Documents\AI_Projects\Varie\ActivityLog\commesse.json" --out foglio.md
```

`--config` va **sempre** passato: senza, oltre ai contesti si perde anche la
sorgente VM, e le ore dentro TIA Portal tornano indistinte.

**Prima di un consuntivo che copra giorni dal 24/08/2026, verifica la
copertura degli eventi nel database VM in sola lettura.** La data del file
`ActivityLog/vm_data/peewee-sqlite.v2.db` è solo un indizio: una copia fatta
oggi può contenere eventi fermi settimane prima. Controllare inizio/fine
degli eventi del bucket finestra, l'eventuale ultimo giorno parziale e i
buchi nel periodo richiesto. Matteo copia il file a mano, una volta al mese.
Dove non copre il periodo resta il contesto host, da dichiarare come tale;
lo script avvisa quando il file manca, non quando è vecchio o incompleto. La procedura di copia
è in [references/sorgente-vm.md](references/sorgente-vm.md). `--giorno YYYY-MM-DD`, `--mese
YYYY-MM`, oppure `--da ... --a ...`. `--consuntivo` produce il file aziendale
invece del foglio di lavoro.

La mappa codice→cliente è in cache (`.mappa_cache.json`) e si aggiorna da
sola ogni 7 giorni. `--rimappa` forza la ricostruzione subito — usalo quando
compare una commessa nuova che vuoi vedere già nel prossimo report.

Lo script lavora **in sola lettura**: API su `localhost:5600` in GET, fallback
SQLite in `mode=ro`. Non scrive mai sui dati di ActivityWatch. Non rimuovere
questo vincolo.

`aw_report.py` è la libreria di acquisizione e riconoscimento commesse, non si
esegue da sola. Dopo aver toccato le sue regex, esegui `test_estrazione.py`:
copre i falsi positivi già trovati nei log veri (IP, numeri di build, modelli
`T450`, pagine HMI). Il caso più insidioso è che la regola che elimina `T450`
cancella anche `Zilme**t**347`, cioè la commessa con più ore in assoluto.

## Report giornaliero: uno solo, schematico

Quando Matteo chiede la giornata, produrre **un report privato semplice**,
con tre parti:
1. **Orario rilevato**: inizio/fine e pranzo al minuto; timeline in fasce di
   **30 minuti**, con attività e commesse principali. Niente lista di tutti
   i cambi finestra, secondi, JSON o allegati grezzi salvo richiesta.
2. **Ore per commessa**: attribuzione interna a **10 minuti**, poi totale
   finale **arrotondato a 30 minuti** con distribuzione dei resti; mostrare
   anche il netto della cornice e lo scarto. Se una voce breve si perde nel
   riepilogo arrotondato, indicarla in una nota senza inventare mezz'ore.
3. **Distrazioni / affari personali**: periodi leggibili e durata stimata,
   separando personale confermato, probabili distrazioni e contenuti ambigui.
   Altro, AI, YouTube e AFK non equivalgono da soli a tempo perso. Tutorial
   tecnici e rendicontazione restano lavoro o formazione, secondo contesto.

I titoli e le chat servono alle verifiche, non devono riempire il report.
La timeline da 30 minuti è solo presentazione: non si rivota ogni mezz'ora,
non si forza una sola commessa nella riga e non si ricalcola il totale dalle
fasce visualizzate. Inizio, fine e pause restano quelli rilevati/confermati.

Il consuntivo aziendale `log/YYYY-MM.md` si genera **solo quando richiesto**
con `--consuntivo`: contiene ore per commessa, senza titoli privati, messaggi
personali o dettaglio distrazioni. Conservare i report storici; il nuovo
metodo si applica ai nuovi conteggi e ai riesami espressamente richiesti.

## Categorie

Sono quelle che Matteo ha definito nella UI di ActivityWatch, lette a runtime da
`settings.json`. **Non inventarne di nuove e non modificare quel file.** Se
un'app non è coperta resta `Non categorizzato`: è un'informazione utile — dice
dove le sue regole non arrivano — non un buco da tappare.

## Attribuzione: una regola sola

**La giornata si divide in slot di 10 minuti: ogni slot va alla voce con più evidenze. Il riepilogo finale resta arrotondato a mezz’ore.**

Votano solo i blocchi che portano una prova:

1. **Un codice commessa nel titolo**, presente in mappa. Vale ovunque: browser
   (`0366 - CEB SPA - SCARICATORE PROFILI`), Excel (`366 - In-Out PLC.xls`),
   non solo negli ambienti di sviluppo.
2. **Un contesto dichiarato** in `commesse.json` (l'IP del Desktop Remoto, il
   nome di una VM).
3. **Un ambiente di sviluppo aperto**, anche senza nome progetto nel titolo
   (`Auto Connect Project` di Sysmac): vale per la commessa più vicina della
   stessa piattaforma, perché un progetto Omron non si apre in TwinCAT.
4. **Una ricerca su un'altra piattaforma**: se il blocco parla di Beckhoff
   mentre attorno c'è Omron, diventa `Ricerca Beckhoff/TwinCAT` invece di
   finire nella commessa sbagliata.
5. **Un'attività personale**, che vota per `Altro`.

Tutto il resto — `claude.exe` / `Codex.exe` con titolo generico, un PDF, una cartella —
resta muto e si accoda allo slot da 10 minuti vinto.

Questa regola ha sostituito l'ereditarietà a 60 minuti, che sui giorni densi
tirava ore estranee nella commessa più vicina: sul 04/08 dava 7h di SMEG contro
5h reali. Il calcolo a 10 minuti e la presentazione a 30 minuti sono distinti. I resti del riepilogo finale sono distribuiti
perché la somma torni al totale giornaliero arrotondato alla mezz'ora.
Il totale netto al minuto resta distinto: sul mese gli scarti giornalieri
possono accumularsi e vanno mostrati.

Quando più del 30% degli slot di 10 minuti non contiene nessuna prova, il foglio lo
scrive in chiaro: quel giorno la proposta va rivista prima di consegnarla.

## Cosa dire sempre

- **Le righe dedotte** con peso rilevante, perché sono quelle da correggere.
- **La pausa dedotta**, quando non è stata trovata nei dati: può dipendere
  da una finestra rimasta aperta o da dati AFK incompleti, non prova lavoro
  continuativo né una causa specifica.
- **Il lavoro invisibile**, che dal 24/08/2026 è invisibile solo a metà. Dentro
  la VM il titolo di TIA Portal porta il percorso completo del progetto
  (`...\370 - LINEA PIANI COTTURA SMEG\...`), quindi quelle ore hanno una prova
  diretta e non vanno più dichiarate come vuoto. **Resta invisibile il Desktop
  Remoto**: `mstsc` verso `192.168.1.106` mostra l'IP e non la macchina, e lì
  c'è solo il contesto. Per i giorni precedenti al 24/08/2026 vale ancora tutto
  il vecchio discorso: dichiara il vuoto, non indovinare.
- **Le finestre mute dentro la VM.** `claude.exe`, `Codex.exe` e `explorer.exe` girano anche
  nel guest e non dicono niente da soli: tengono la commessa solo perché il
  titolo dell'host viene conservato in coda (`[VM] Claude · Siemens - VMware
  Workstation`). È un aggancio di contesto, non una prova — trattalo come tale.
- **Claude e Codex possono esporre solo un titolo generico**, mentre
  Antigravity può mostrare il nome della conversazione. Senza contenuti chat
  verificati, l'attribuzione resta per contesto temporale, non prova diretta.

## Onestà

I log dicono quale finestra era in primo piano, non cosa stava facendo Matteo.
Scrivi "compatibile con attività di collaudo", non "ha eseguito il collaudo".
Un totale sbagliato in un rendiconto aziendale costa più di cinque minuti di
verifica: se un numero sorprende, rilancia lo script su quel giorno e guarda la
timeline prima di consegnarlo.

## Configurazione

I collegamenti di riconoscimento (contesti, nomi, marcatori confermati)
stanno in `ActivityLog/commesse.json`, mai come patch ad hoc nel codice.
Le correzioni di orari, pause e viaggio vanno nel prospetto di revisione
con data e fonte: lo schema attuale della configurazione non le importa.
Passalo sempre con `--config`.

```json
{
  "contesti": [
    {"pattern": "192\\.168\\.1\\.106", "commessa": "370 SMEG"},
    {"pattern": "Siemens - VMware Workstation", "commessa": "370 SMEG",
     "da": "2026-05-01", "a": "2026-12-31"}
  ],
  "vm": [
    {"pattern": "Siemens - VMware Workstation",
     "db": "vm_data/peewee-sqlite.v2.db", "da": "2026-08-24"}
  ],
  "personale": ["porte rototraslanti", "climaimpianti"],
  "commesse": {"370": "SMEG", "348": "Zilmet"},
  "ignora": ["450"]
}
```

`vm` collega la finestra di una macchina virtuale sull'host alla copia del suo
database. `db` è relativo alla cartella di `commesse.json`. Il `pattern` deve
individuare **quella** VM e non una qualsiasi: sul PC di Matteo gira anche
`AddSpaceWindows 11 x64`, e un pattern generico su `vmware.exe` sposterebbe le
sue ore dentro la commessa di SMEG. `da` protegge i mesi consuntivati prima che
il watcher esistesse.

Il contesto con lo stesso `pattern` **resta** dopo l'installazione del
watcher: è il terzo livello, quello che copre gli intervalli senza dati VM.
Se la VM cambia progetto, delimitare comunque la validità con `da`/`a`.

`commesse` impone il nome della commessa. Per il **370 è obbligatorio**: i
titoli di TIA Portal contengono `370 - LINEA PIANI COTTURA SMEG`, mentre i
contesti producono la stringa `370 SMEG`. Senza l'imposizione la stessa
commessa uscirebbe con due etichette diverse e nel consuntivo comparirebbe come
due voci separate. Quando aggiungi una VM nuova, controlla sempre che nome
genera il riconoscimento e allinealo a quello dei contesti.

`contesti` è il pezzo più importante: collega una finestra che non dichiara il
progetto (un IP di Desktop Remoto, il nome di una VM) alla sua commessa. È un
collegamento che solo Matteo può fare. **Usa sempre `da`/`a` quando quel PC o
quella VM cambieranno progetto**, altrimenti riscrivi la storia dei mesi già
consuntivati.

`personale` esclude dall'ereditarietà attività che non sono lavoro. Serve
perché un blocco personale vicino a una commessa verrebbe altrimenti assorbito.

## Quanto ci si può fidare

Confronti storici, eseguiti con il precedente metodo a mezz’ore, contro tre giornate ricostruite a mano da Matteo. Non costituiscono validazione del nuovo passo da 10 minuti. La cornice è
una stima, da verificare quando la copertura è scarsa; la ripartizione è
una proposta.

| Giorno | Proposta | Reale | Scarto |
|---|---|---|---|
| 24/06 | 366 `3h` · 365 `2h30` · Altro `1h30` · Ricerca `1h` | `3h30` · `3h` · `1h` · `30m` | ≤30m su tutte |
| 04/08 | SMEG `6h` · Hager `1h` · Altro `1h` | `5h` · `1h` · `2h` | Hager esatta |
| 08/07 | SMEG `2h30` · Altro `3h` · Minifaber `30m` · Zilmet `1h` | `4h30` · `2h` · `1h` · — | SMEG −2h |

Nei casi calibrati il totale era compatibile con le ricostruzioni di Matteo.
Questo non garantisce tutte le giornate: il 27/07/2026 la cornice indicava
8h04 ma fra 08:17 e 14:02 c'erano circa 4 minuti di eventi. La presenza
dichiarata in officina spiega un vuoto, non prova otto ore al PC.
La ripartizione può sbagliare di mezz'ora per voce e anche molto di più.

Sbaglia molto di più quando gran parte del lavoro passa da una finestra muta
(VM, Desktop Remoto, `claude.exe` / `Codex.exe`) e attorno non c'è nulla che ancori. L'08/07
il tempo con prove di SMEG era 68 minuti su 4h30 reali: il resto era
Antigravity e Thunderbird, che non dicono niente. In quei casi non c'è regola
che tenga, e la correzione è manuale.

Dal 24/08/2026 la VM toglie una fetta di quel problema, ma non lo risolve:
dentro il guest TIA Portal dichiara il progetto, i client AI generici no. Il 17/09
sono 68 minuti di TIA Portal con prova diretta contro 45 minuti di Claude
muto, nello stesso pomeriggio. Sul consuntivo il guadagno si vede poco —
agosto esce identico a prima, perché il contesto stava già indovinando giusto
— e si vede invece dove il contesto sbagliava: sempre il 17/09, mezz'ora che
il contesto dava a SMEG è tornata a 344 CBL srl, che quel giorno aveva dieci
minuti di prove vere in Sysmac. Il valore della VM non è sommare ore, è
smettere di attribuirne di sbagliate.

**Voci deboli**: una commessa con meno di 15 minuti di prove nella giornata
resta nel calcolo, ma può vincere soltanto gli slot di 10 minuti in cui
compare davvero, senza assorbire slot muti. Se attraversa due slot, può
vincerli entrambi; il riepilogo finale a mezz'ore può assorbire una voce breve.
Indicare il riferimento breve in nota quando necessario.

**Orario di lavoro**: nessuna attività prima delle 7:00 o dopo le 20:00 viene
mai contata — per dichiarazione esplicita di Matteo, non è fisicamente lavoro.
Il taglio avviene sui blocchi stessi, prima di ogni altro calcolo: un programma
rimasto acceso a notte fonda non compare né in timeline né nel totale.

**Pausa**: riconosciuta dal bucket AFK solo se dura tra 1 e 3 ore e inizia
nella fascia 11:00–15:30. È un'assenza misurata interpretata come pranzo,
da distinguere dal default dedotto senza eventi. Sopra le 3 ore
non viene accettata come pausa pranzo: può essere fine giornata o un'assenza
più lunga (weekend, ponte, malattia). Non si sottrae come pranzo; il motore
non taglia automaticamente la giornata all'inizio di quell'assenza.
Controllare la fine sugli eventi reali e sulle dichiarazioni di Matteo. Sotto
un'ora è una pausa breve, non pranzo. Se il lavoro non attraversa il
mezzogiorno (es. un pomeriggio iniziato alle 15:47), non si deduce nessuna
pausa di default: dedurne una porterebbe a un totale negativo o assurdo.

Non presentarla mai come un dato misurato: è una proposta costruita su una
maggioranza per slot di 10 minuti, e su alcuni giorni sbaglia. Il foglio di lavoro serve
proprio a farla correggere.

## Analisi del tempo non attribuito

Quando Matteo chiede "quanto Altro faccio", "quanto è personale" o simile
(non un consuntivo per commessa, ma un'analisi del pool non attribuito nel
tempo), non equiparare `Altro` a svago. `scripts/analisi_altro.py` è una
fotografia storica del **01/10/2025–06/08/2026**, senza innesto VM;
produce per quel periodo: totale e
media giornaliera del pool "senza aggancio", i giorni di picco, le app che lo
compongono, e un campione dei titoli Chrome più pesanti dentro la parte "non
attribuita" — perché nessun automatismo può giudicare se un titolo è lavoro o
svago, va mostrato a Matteo e basta.

```powershell
python "${CLAUDE_SKILL_DIR}\scripts\analisi_altro.py"
```

**Confronto storico**: nell'analisi del 06/08/2026 il pool senza aggancio
valeva 2,48 h/giorno contro 1,42 h/giorno di `Altro` nei report. La regola
di vicinanza assegna parte dei blocchi muti alle commesse, quindi queste
misure non sono equivalenti. Quando Matteo chiede ore «non giustificate»,
mostrare separatamente tempo senza aggancio, attribuzioni dedotte e
personale confermato. Né il pool né `Altro` misurano lo svago o l'assenza
di una giustificazione lavorativa. I valori storici non si proiettano sui
nuovi periodi.

Il motore classifica anche YouTube e alcune app/categorie come personali
per regola. Per una stima di svago reale riesaminare i contenuti e le
conferme di Matteo: tutorial tecnici, formazione e contenuti ambigui non
sono automaticamente tempo perso. Per i limiti di periodo e classificazione
leggere [references/rendicontazione.md](references/rendicontazione.md).

**Marcatori personali**: quando Matteo conferma che un titolo ricorrente è
personale (è già successo con Google News, un sito di un comune, un contatto
chiamato "Roby"), aggiungilo a `personale` in `commesse.json` — non decidere
da solo cosa è personale, e non aggiungere pattern basati su un'ipotesi. Il
pattern viene cercato dentro `"nome_app titolo"` concatenati: **non usare mai
`^` o `$`**, l'ancora andrebbe contro il prefisso dell'app e il marcatore non
scatterebbe mai (bug reale, trovato e corretto in sessione).

Il dettaglio dei filtri di riconoscimento è in
[references/riconoscimento.md](references/riconoscimento.md).
