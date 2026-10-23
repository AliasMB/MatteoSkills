# Formato interno Sysmac Studio (ricostruito, non documentato da Omron)

Verificato il 2026-10-19 su cache Solution (progetto 175, Sysmac per NX1P2 v1.14) e 8 repo VC (332, 335, 337, 349, 350, 353, 365, 366, 371).

## Cartelle
- `C:\OMRON\Data\Solution\<GUID>\` — cache di ogni soluzione aperta/importata. Un file per entità: `<entityId>.xml` più estensioni accessorie (`.BookmarkGroup`, `.dat`, `.drive`, `.param`...).
- `C:\OMRON\Data\VC\<nome>\Project\` — stessa struttura per i progetti sotto version control (Git).
- `<GUID>.manifest2` — `solutionName`, `ApplicationFeature name="SetUnit <CPU> Ver. x.y"`.
- `<GUID>.oem` — albero delle entità: `Entity` annidati in `ChildEntities`, attributi `id`, `type`, `subtype`, `name`. È l'unica fonte dei nomi: i file XML hanno nome = id.
- `*.applicationlock` — soluzione aperta in Sysmac.
- `.smc2` — archivio ZIP della soluzione (stessi file sotto una cartella GUID). Non gestito dallo script.

## Entità utili (`type` nell'.oem)
| type | contenuto |
|---|---|
| `Program` / `FunctionBlock` / `Function` | nodo POU; `subtype` = linguaggio (`MultipartLadder`, `Ladder`, `StructuredText`, `FBDExtended` = safety) |
| `Variables` (figlio del POU) | variabili locali, formato SLWD |
| `PouBody` (figlio del POU) | corpo/sezione: JSON ladder o `<StructuredTextModel>` |
| `Variables` sotto Dati | variabili globali (SLWD) |
| `DataType` | tipi dati, XML `<DataType>` annidati; `IsControllerDefinedType="true"` = di sistema |
| `NexTask` | task: `TaskExecutionCondition` (µs), `ExecutionPriority`, `AssociatedProgramData ProgramName` |
| `PouBodySourceHolder`, `SourceHolder`, `Inline`, `BookmarkGroup` | dati di compilazione/editor, ignorati |

## SLWD (variabili)
```
[SLWD version=1.0]
_EN=Variables
+GN=VAR	GVT=DefaultGroup
++D=BOOL	N=Alarm	G=VAR	Com=Asse in allarme
```
Chiavi: `D` tipo, `N` nome, `G` sezione (VAR, VAR_INPUT, VAR_OUTPUT, VAR_IN_OUT, VAR_EXTERNAL, VAR_GLOBAL), `Com` commento, `IV` valore iniziale, `R=1` retain, `Const=1`, `RO=1`, `AT` indirizzo I/O, `NTP` pubblicazione rete (PublicationOnly/Input/Output), `E=UpDirection` fronte, `EC` commenti per elemento (`<EC EK="bit[0]" C="..."/>`), `Ord` ordine.

## Ladder (PouBody)
Una riga JSON per rete: `{"CLs":[...], "CMT":"commento", "LRI":n, "RRI":n, "VLs":[...]}`.
- Griglia: ogni elemento occupa la cella `(X,Y)` (default 0). F/FB occupano una sola riga logica.
- Nodo `N(x,y)` = lato sinistro della colonna x sulla riga y. Un elemento in `(x,y)` va da `N(x,y)` a `N(x+1,y)`. La colonna 0 è alimentata dalla barra sinistra.
- `VLs: {"X":x,"Y":y}` = collegamento verticale tra `N(x,y)` e `N(x,y+1)` (OR delle potenze in arrivo).
- `__type`:
  - `LD` contatto: `Var`, `Not`, `Up` (fronte salita), `Dwn` (fronte discesa), `Id` per i fronti.
  - `ST` bobina: `Var`, `S` set, `RS` reset, `Not` negata, `Up` su fronte.
  - `HL` linea orizzontale (passa la potenza).
  - `F` funzione / `FB` blocco funzione: `Name`, `Var` (istanza FB), `In`/`Out` con `PF` (pin di potenza: EN/ENO, In/Q, Enable...) e `PRM` (`Arg`, `Var`, `Type`, `IO` = in-out, `Not`, `Up`). `PL:true` = funzione usata come contatto (confronti `=`, `<`, `>=`...).
  - `IST` ST inline: `TXT`.
  - `JMP` salto: `Label`.
- Commenti e testi con escape `\uXXXX`.

## ST
`<StructuredTextModel ...><Text>codice</Text></StructuredTextModel>` (entità XML-escaped).

## Protezione
Corpo cifrato: `<EncryptedFile><EncryptionLock>...<Body>base64` (anche annidato e escaped dentro `StructuredTextModel`). Non decifrabile: serve togliere la protezione in Sysmac.
