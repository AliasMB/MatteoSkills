# Compilare e collaudare un PLC TwinCAT 3

## Prima del test

1. Individua il comando di collaudo del progetto. Per una suite esistente usa il suo script, per esempio `ci.cmd` in Takumi, con le condizioni del relativo runbook. Per una prova di macchina usa i comandi pubblici del PLC e i riscontri NC o I/O previsti dal test.
2. Verifica build XAE e runtime, versioni delle librerie, piattaforma, AMS Net ID e licenze sul target effettivo. Su UmRT 4026 seleziona `TwinCAT OS (x64)` e verifica l’istanza dedicata prima di attivare. La licenza di un’altra istanza o di una configurazione precedente può essere diversa.
3. Conserva CRLF e BOM dei file TwinCAT. Per un PLC nuovo parti da `TIPC.CreateChild` con il template Beckhoff e usa come base i GUID, i task e i riferimenti XTI generati. Se modifichi un .plcproj, verifica che abbia al massimo un blocco `ProjectExtensions`. [Creazione del progetto PLC](https://infosys.beckhoff.com/content/1033/tc3_automationinterface/21842439947.html)

## Ticket PLC in parallelo

Prima di dividere i ticket PLC, individua chi scrive i consensi e chi comanda il gruppo NC. Se ciclo CN e jog condividono uno di questi punti, assegna la logica condivisa a un solo esecutore. Concorda con gli altri i comandi e gli stati che ciascun ticket può usare.

## Compilazione e prova

1. Quando disponibile, esegui il controllo ST del progetto, per esempio `plc.py check --sln <soluzione.sln>`. Compila poi con lo script del repository o con Automation Interface. Il parser ST verifica la sintassi dei corpi. La compilazione verifica tipi, riferimenti e membri.
2. Su XAE Shell 64 bit 4026 usa il ProgID `TcXaeShell.DTE.17.0` dalla vista del registro a 64 bit. Se la build DTE sincrona si blocca, prova `SolutionBuild.Build(false)` e attendi `BuildState = 3` con un timeout. Verifica `LastBuildInfo = 0` e la generazione degli artefatti attesi per i progetti modificati, per esempio `.tmc` e `.compileinfo`. Un risultato no-op o un conteggio senza artefatti richiede una verifica. [ProgID Beckhoff](https://infosys.beckhoff.com/content/1033/tc3_automationinterface/242746251.html) · [Output e lista errori DTE](https://infosys.beckhoff.com/content/1033/tc3_automationinterface/21842703115.html)
3. Prima dell’attivazione confronta Net ID e piattaforma con il target autorizzato. Dopo l’attivazione verifica che il runtime sia in Run e che usi il progetto e l’applicazione appena compilati. Per il collaudo virtuale mantieni il test sull’istanza di simulazione.
4. Per TF1140 avvia lo script di progetto o `TcTestClientCli` con il target esplicito e controlla esito e report della prova corrente. Per ADS, campiona comandi, stati ed esiti effettivi. Mantieni pressione e rilascio oltre il tempo di scansione del task. In ProgettoCN, 100 ms di rilascio su task da 10 ms hanno evitato due scritture nello stesso scan. Al termine rilascia i comandi di prova.
5. Riporta a parte ciò che è stato verificato in compilazione e ciò che è stato osservato sul runtime. Indica target, versioni e risultati correnti.

Nel collaudo di una ciclica, dopo la fine del movimento verifica che la macchina a stati torni a riposo con le condizioni iniziali ripristinate, pronta per un nuovo ciclo.

## Errori già osservati

| Sintomo | Primo controllo |
|---|---|
| `symbol description does not match` dopo l’attivazione in UmRT | Controlla `TwinCAT OS (x64)`, Net ID e applicazione realmente caricata. Con la piattaforma RT attiva il dialogo headless può lasciare sul target una combinazione incoerente di PLC e configurazione. |
| Build bloccata all’apertura o modale `ProjectExtensions` | Controlla che il progetto non sia già aperto e che il .plcproj abbia un solo `ProjectExtensions`. XAE può averlo scritto in un tentativo precedente. |
| `LinkVariables` non trova il ramo NC | Enumera i nodi COM e leggi `PathName`. In ProgettoCN il canale GST è direttamente sotto il task SAF, al percorso `TINC^NC-Task 1 SAF^Interpolation`. |
| Due scritture ADS consecutive producono un solo fronte | Aggiungi un rilascio osservabile dal PLC prima del nuovo Start e verifica la risposta sullo stato pubblico. |

Se Automation Interface e log non bastano, usa XAE visibile come ultima opzione. Per leggere diagnostica su una soluzione che potrebbe essere bloccata, usa una copia temporanea. Quando lavori per Matteo in Codex, delega mouse e tastiera a Terra Medium.
