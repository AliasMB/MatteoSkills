---
name: omron-sysmac
description: "Legge, cerca e confronta progetti Omron Sysmac Studio (NJ/NX) dalla cache C:\\OMRON\\Data, con ladder convertito in espressioni. Usa per codice, variabili, POU, reti ladder o FB di un PLC Omron, anche \"dove viene usata la variabile X\"."
---

# Omron Sysmac — consultazione progetti

Script: `${CLAUDE_SKILL_DIR}/scripts/sysmac.py` (Python stdlib, lanciare con `python -I`). Sola lettura su `C:\OMRON\Data`.

## Workflow

1. **Trova il progetto**
   ```
   python -I ${CLAUDE_SKILL_DIR}/scripts/sysmac.py list <filtro>
   ```
   Righe: GUID breve, data `.oem`, `APERTO` (lock attivo in Sysmac), sorgente (`SOL` = cache Solution, `VC:<cartella>` = repo version control), nome soluzione, CPU.
   Più versioni della stessa commessa: di solito la più recente / quella APERTA. Se non è ovvio quale versione intende Matteo, chiediglielo prima di analizzare.

2. **Esporta** (rigenera sempre: è veloce e la cache cambia mentre Matteo lavora)
   ```
   python -I .../sysmac.py export <guid8|percorso|filtro> [--out DIR] [--latest]
   ```
   Default: `AI_Projects/OMRON/<num>_<cliente>/export_<versione>/`. Sovrascrive solo cartelle già generate dallo script (riconosciute da `manifest.json`).

3. **Leggi `INDEX.md` per primo**: task (periodo, programmi), tabella POU con linguaggio, n° reti/righe e link a ogni sezione, link a variabili globali, tipi, config.

4. **Cerca, non leggere tutto**: usa Grep su `pou/` per la variabile, poi apri solo le sezioni coinvolte.
   - chi la scrive (ladder): `-> (=|=NOT|S|R) NomeVar\b`; (ST): `NomeVar\s*:=`; uscita FB/funzione: `=>\s*NomeVar\b`
   - chi la legge: `\bNomeVar\b` nelle righe condizione
   - dichiarazione: `vars/` (globali), `pou/<...>/_variabili.st` o testa del file POU (locali), `types.st` (struct/enum)

5. **Rispondi con riferimenti puntuali**: `Programma / sezione / R<n>`, variabile, valore. Matteo applica lui le modifiche in Sysmac Studio: non modificare mai i file in `C:\OMRON`.

## Struttura export

```
INDEX.md                     indice (leggere per primo)
pou/Programmi/<Prog>.st      POU a sezione singola: VAR + corpo
pou/Programmi/<Prog>/        POU multi-sezione: _variabili.st + NN_<Sezione>.st
pou/Blocchi_funzione/...     FB / funzioni
vars/<gruppo>.st             variabili globali (AT, RETAIN, NET-Input/Output, commenti per elemento)
types.st                     tipi utente (STRUCT/UNION/ENUM), esclusi quelli di sistema
config/INDEX.md + *.txt      configurazione (assi, EtherCAT, EIP, eventi, trace...) in XML compattato
manifest.json                GUID entità -> percorso logico -> file -> sha256
```

Nei POU, `VAR_EXTERNAL (globali usate): ...` elenca solo i nomi: tipi e commenti stanno in `vars/`.

## Legenda ladder

```
R12 // commento rete
  ResetGen AND Fasi[2] AND (Auto AND Remote OR Manual)    <- condizione di potenza
    -> R Fasi[2]                                          <- reset
    -> S Fasi[3]                                          <- set
  T_Attesa(In:=Fasi[13] OR Fasi[30], PT:=T#500ms) : TON   <- chiamata FB (sempre eseguita)
```
- `-> = X` bobina, `-> =NOT X` bobina negata, `S`/`R` set/reset, `↑x`/`↓x` contatto fronte salita/discesa, `↑(cond)` bobina su fronte.
- FB: il primo ingresso (`In`, `Enable`, `Execute`...) riceve la condizione; contatti dopo il FB leggono `Inst.Q` (uscita di potenza).
- Funzioni con EN: `-> MOVE(In:=0, Out=>X)` eseguite se la condizione è vera; dopo una funzione la potenza prosegue uguale alla condizione (ENO assunto = EN).
- Confronti in linea: `(a >= b)` come contatto.
- `ST:` testo ST inline nella rete.
- Le azioni sono nell'ordine di esecuzione (alto→basso); condizioni uguali consecutive sono raggruppate.
- `?LADDER-RAW (motivo)`: topologia non risolta; seguono gli elementi con coordinate `@x,y` e i collegamenti verticali `VL`. Ragiona sugli elementi, non inventare la logica.

## Limiti (dichiararli quando incidono sulla risposta)

- Formato interno Omron non documentato: la conversione ladder è ricostruita dalla griglia. Per decisioni critiche (sicurezze, movimenti) chiedi a Matteo di confermare la rete in Sysmac.
- POU con protezione: `[POU PROTETTO - corpo cifrato]`, illeggibili finché Matteo non toglie la protezione.
- POU safety (FBDExtended) e librerie esterne: non in XML, segnati in INDEX come "non in XML".
- Pagine HMI NA, Data Trace, parametri drive finiscono in `config/` così come sono (XML compattato).
- La cache Solution è una copia di lavoro: può contenere modifiche non salvate in `.smc2` o non caricate sul PLC. Il nome in `manifest2` può differire da quello nell'`.oem`.
- Archivi `.smc2` (Dropbox) non gestiti: Matteo deve aprirli in Sysmac per farli comparire in cache.

## Confronto versioni

```
python -I .../sysmac.py export <guidA> --out <dirA>
python -I .../sysmac.py export <guidB> --out <dirB>
python -I .../sysmac.py diff <dirA> <dirB>
```
Confronta per entità (GUID stabili tra copie della stessa soluzione): elenca entità aggiunte/rimosse e il diff testuale dei soli file cambiati, con le reti già in forma di espressione.

Dettagli sul formato raw (`.oem`, SLWD, JSON ladder, cifratura): `references/formato-sysmac.md`.
