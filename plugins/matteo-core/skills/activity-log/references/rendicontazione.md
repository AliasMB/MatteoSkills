# Dichiarazioni, trasferte e giustificazione delle ore

Leggere questa reference quando Matteo corregge orari o pause, chiede ore
presso un cliente, viaggio, lavoro senza PC, temi delle chat o inefficienze.
Le correzioni qui descritte si applicano nel report di revisione: gli script
attuali non importano automaticamente dichiarazioni, viaggio o contenuti chat.

## Quattro misure distinte

| Misura | Fonte e limite |
|---|---|
| Cornice stimata | Prima/ultima attività host meno pausa; può includere vuoti del watcher, attese e lavoro senza PC. Non certifica presenza continua al PC. |
| Ore per commessa | Proposta calcolata a 10 minuti, poi arrotondata a mezz’ore, comprese attribuzioni per contesto o vicinanza. Non è una misura diretta. |
| Presenza presso il cliente | Fasce dichiarate da Matteo, al netto di pause e viaggio già inclusi. Può comprendere lavoro su altre commesse durante le attese. |
| Viaggio | Durata dichiarata, separata dal lavoro presso il cliente; non si ricava dagli orari della prima/ultima finestra. |

Una fascia dichiarata senza eventi è una dichiarazione valida, non zero ore
perché il PC era spento. Un intervallo senza eventi, da solo, non dimostra né
lavoro né svago. Controllare i dati grezzi nei vuoti lunghi: la soglia del 30%
di slot di 10 minuti senza prove segnala l'attribuzione debole, non misura la copertura
del watcher. Anche una giornata attribuita interamente da un contesto può
avere ore senza registrazioni effettive.

## Correzioni e pause

La correzione esplicita più recente di Matteo prevale sulla sua annotazione
precedente e sulle deduzioni automatiche. Conservare valore originale, valore
corretto, fonte e date coinvolte. Non estendere una correzione locale a tutti
i giorni o a tutte le trasferte.

La durata effettiva del pranzo identificata nei dati o confermata da
Matteo è il valore da sottrarre. Il default 1h30 è soltanto il ripiego
quando manca una durata attendibile, non una pausa da imporre.

- **Pausa dedotta:** il motore usa 1h30 quando la cornice contiene
  12:30–14:00 e non trova un'assenza compatibile. Se Matteo dichiara una pausa
  diversa per quelle date, sostituire la deduzione; una sola mattina o un solo
  pomeriggio non richiede una pausa fuori dalla fascia lavorata.
- **Pausa da AFK:** è un'assenza registrata e interpretata come pranzo,
  non una prova del motivo dell'assenza. Una dichiarazione generica «circa 1h»
  non basta a ridurre automaticamente tutte le assenze misurate. Segnalare il
  conflitto; se Matteo conferma per quel giorno lavoro sul robot/officina
  durante parte dell'assenza, correggere quella parte come lavoro dichiarato.
- Il resto dell'AFK non si sottrae indiscriminatamente: lettura schemi,
  osservazione macchina e collaudo possono avvenire senza mouse/tastiera.

Esempio reale SMEG: 7h35 nette con pausa **dedotta** 1h30 diventano 8h05
con pausa dichiarata 1h (**+30m**). Il 21/09/2026 Matteo ha dichiarato «1h,
ma mai precisa» per quelle trasferte; il recupero riguardava cinque giorni,
quindi +2h30. L'assenza AFK di 2h09 del 10/08 resta distinta: recuperare
1h09 richiede chiarire cosa avveniva in quel periodo.

## Trasferte, viaggio e sovrapposizioni

Prima del calcolo, chiarire se la fascia dichiarata comprende viaggio e
pause. Usare la stessa base temporale per confrontare dichiarazioni e log.

Un inizio più tardi del solito (per esempio alle 09:00) o una fine
anticipata possono suggerire un viaggio. Segnalare l'ipotesi e chiedere
sempre conferma a Matteo prima di conteggiarlo: se c'è stato, quanto è
durato e se è già compreso nella fascia dichiarata. Gestire ogni caso
separatamente; gli orari del PC non bastano a decidere né durata né
tratta, e nessuna ora di viaggio ipotizzata entra nel totale in attesa
della conferma.

```text
fascia comprensiva di viaggio:
presenza cliente netta = fine − inizio − pausa compresa − viaggio compreso
totale netto = presenza cliente netta + viaggio

viaggio fuori dalla cornice ActivityWatch:
totale revisionato = cornice netta + correzioni documentate + viaggio aggiuntivo
```

Non sommare alla presenza dichiarata le ore ActivityWatch che cadono già in
quella fascia. Non aggiungere nuovamente viaggio già incluso. Se le ore
di altre commesse sono comprese nella presenza presso il cliente, mostrare
la sovrapposizione: non imputare lo stesso intervallo due volte. La presenza
in officina non autorizza ad assegnarla tutta alla commessa del cliente.

Esempio Moretto: fascia corretta **20/07/2026 13:30–17:30**, comprensiva
di 30m andata e 30m ritorno, significa **3h in officina + 1h viaggio**,
senza detrarre pranzo. Non significa automaticamente 3h di lavoro esclusivo
sulla commessa 175. Matteo ha confermato che riferimenti al robot Hyundai
sostengono il collegamento a Moretto nel contesto di quel lavoro: senza
orari dichiarati non bastano a quantificare altre visite, né a creare un
contesto universale per qualsiasi titolo «Hyundai».

Per SMEG il 21/09/2026 sono state dichiarate **8h aggiuntive di strada**:
2h per tratta, su 24 e 26/08, 07 e 10/09. È un caso specifico, non 8h per
qualsiasi trasferta e non 2h per ognuno dei dieci giorni. Nel riesame del
29/09 Matteo ricorda due giornate solo mattutine senza identificarle:
tenere il punto aperto, senza scegliere le date dai log o chiamare tutte
le giornate «piene».

## Chat, formazione e navigazione personale

Claude e Codex possono mostrare un titolo generico; Antigravity può esporre
il nome della chat. Per giustificare temi e interventi, leggere i contenuti
delle conversazioni disponibili e confrontarli con la timeline. Convertire
i timestamp in **Europe/Rome**, distinguere host/VM e deduplicare messaggi
importati o esportati più volte. Tenere fonte, data e messaggio umano che
sostiene l'argomento; una risposta dell'assistente o un titolo generico da
soli non provano che il lavoro sia stato eseguito.

Due messaggi SMEG alle 09:00 e alle 16:00 provano riferimenti puntuali,
**non sette ore continue**. Le chat chiariscono argomenti e contesto; non
generano ore da sommare ad ActivityWatch. Se raffinano un'attribuzione,
modificare solo l'intervallo sostenuto dalle evidenze e spiegare la revisione.

Per analizzare inefficienze distinguere lavoro di commessa, formazione
generale, rifacimenti documentati, personale confermato e contenuti ambigui.
Sono distinzioni del report, non nuove categorie da scrivere in ActivityWatch.
Formazione tecnica non equivale a svago; un rifacimento non dimostra da solo
tempo sprecato. YouTube, browser, AI o AFK da soli non provano attività
personale. Non sottrarre da una commessa quote di personale/ formazione
stimate su un altro periodo o già escluse dal suo conteggio.

**Limiti degli script attuali da verificare prima di usarne i numeri:**

- `analisi_altro.py` è un'analisi storica con date fisse
  **01/10/2025–06/08/2026**, senza innesto VM. Non ha argomenti CLI per
  cambiare periodo. Non presentarla come aggiornata o completa per settembre.
- `e_personale()` in `giornata.py` tratta automaticamente `youtube`, alcune
  app/siti e categorie `Media` / `Comms > IM` come personali. La sua etichetta
  è un risultato della regola, non una conferma umana che ogni contenuto sia
  svago. Riesaminare i contenuti quando Matteo chiede ore personali reali.
- I valori storici 2,48h/giorno senza aggancio e 1,42h/giorno di `Altro`
  non sono coefficienti da applicare ai nuovi mesi. Nessuna prova di commessa
  non significa automaticamente nessuna giustificazione lavorativa.

## Prospetto e verifica

Mostrare separatamente cornice originale, correzioni dichiarate, lavoro
revisionato e viaggio. Usare **h/m**, evitando decimali ambigui. Se non è
noto come ripartire una correzione tra commesse, lasciarla come quota
dichiarata da attribuire; non assegnarla automaticamente al cliente visitato.

Tenere distinti totale netto in minuti e totale per commessa arrotondato:
`arrotonda()` conserva la somma al totale giornaliero **arrotondato** alla
mezz'ora, non necessariamente al minuto esatto della cornice. Sommare le
righe effettive, indicare lo scarto, non aggiungere resti inventati per
forzare l'uguaglianza. Non forzare giornate brevi o lunghe a 8h.

Gli archivi restano in sola lettura e i consuntivi storici si conservano;
salvare un riesame separato, salvo richiesta di aggiornare il file esistente.
Nel documento condivisibile usare descrizioni sintetiche del lavoro,
fonti/provenienza dei conteggi e limiti necessari; titoli privati, messaggi
personali e dettaglio delle inefficienze restano nel foglio privato.
