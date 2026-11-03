# Scrivere un progetto Sysmac da file

Si genera un XML IEC 61131-10 e Matteo lo importa in Sysmac Studio. Non si scrive mai in `C:\OMRON`.

Provato una sola volta: progetto `00380 - HAGER - Colonna saldatura` (CX-Programmer CP1E convertito), Sysmac Studio 1.61, NX1P2-9B40DT1 v1.64. L'import è riuscito e Matteo riferisce che "sembra compilare". Nessuna prova in simulazione o su macchina.

## Stato di ogni funzione

**Provato (importato e riletto dalla cache):**
- ladder multi-sezione (`smcext:LdSection`) con commenti di rete
- contatti normali, negati, sul fronte (`edge="rising"`)
- bobine e `latch="set"` / `latch="reset"`
- rami OR e rami paralleli con condizione comune
- `TON` con istanza locale, `MOVE`, `Inc`, confronti `>=`, `<>`, `<`
- tipo `UNION` con `W : WORD` e `bit : ARRAY[0..15] OF BOOL`, accesso `Var.bit[n]` e `Var.W`
- variabili globali con commento, commenti per elemento, ritenzione
- I/O built-in NX1P2 come indirizzo AT

**Da provare: non abbiamo fatto motion, quindi tutto il resto non è verificato.**
- motion: FB `MC_*`, `_sAXIS_REF`, indirizzi `MC://`
- device variable EtherCAT e NX Unit, variabili EtherNet/IP pubblicate
- FB e funzioni utente, corpi ST, salti, struct ed enum (sono nel `Sample.xml` di Omron, noi non li abbiamo usati)
- altre CPU e altre versioni

Prima di usare una di queste funzioni, copiala da `Sample.xml` se c'è, e dichiara a Matteo che è la prima prova.

**Non si importa da XML:** W504 elenca solo programmi, funzioni, FB, tipi e variabili globali. Configurazione assi, EtherCAT, Unit, task e impostazioni del controller restano da fare in Sysmac Studio.

## Procedura

1. Matteo crea il progetto con la CPU giusta. Controlla la versione: l'import richiede NJ/NX/NY unit version 1.19 o superiore, NX102 1.31, NX502 1.60 (W504 p. 8-146).
2. Leggi il progetto con `sysmac.py export` per avere CPU, task e nomi I/O.
3. Genera l'XML in `AI_Projects/OMRON/<num>_<cliente>/`, con un self-check su XML ben formato e connessioni coerenti. Esempio funzionante: `scripts/cxt_to_iec_xml.py`.
4. Matteo importa: `Tools` > `IEC 61131-10 XML` > `Import`, sceglie il file, `Execute`. Se compare `Compare before importing` controlla le differenze e usa `Overwrite all difference`.
5. Matteo lancia `Project` > `Build Controller` (F8) e riporta errori e warning. Se l'import fallisce, correggi il generatore: non chiedere modifiche a mano.
6. Rileggi con `sysmac.py export` e confronta ogni rete con il sorgente. Dichiara che il file dei risultati di build in cache non dà un esito leggibile.
7. Controlla il programma nel task: in 00380 il programma generato come `Program0` compare come `Main` in `PrimaryTask`, e non sappiamo se sia stato rinominato a mano.
8. Salvare e provare la macchina spetta a Matteo.

**Non pilotare l'import con computer use.** I menu a tendina di Sysmac Studio non compaiono negli screenshot, e due agenti si sono bloccati lì. Chiedi a Matteo di fare i pochi click: è più rapido e costa meno.

## Formato XML

Riferimento: `C:\Program Files\OMRON\Sysmac Studio\Sample\IEC 61131-10 XML\Controller\` (`Sample.xml` e gli schemi `.xsd`).

Struttura:
```
Project
  ContentHeader   smcext:DeviceInfo modelName="NX1P2-9B40DT1" version="1.64"
  Types/GlobalNamespace
    DataTypeDecl                tipi utente (UNION: StructTypeSpec overlap="true")
    Program name="..."
      ExternalVars              una Variable per ogni globale usata dal programma
      Vars accessSpecifier="private"   variabili locali e istanze FB
      MainBody/BodyContent xsi:type="smcext:LdSection" name evaluationOrder
        Rung evaluationOrder
  Instances/Configuration/Resource
    GlobalVars retain="true"    variabili ritentive
    GlobalVars                  variabili normali
```

Una rete collega le uscite e gli ingressi tramite id:
```xml
<Rung evaluationOrder="1">
  <CommonObject xsi:type="Comment"><Content xsi:type="SimpleText">Commento</Content></CommonObject>
  <LdObject xsi:type="LeftPowerRail"><ConnectionPointOut connectionPointOutId="1"/></LdObject>
  <LdObject xsi:type="Contact" negated="true" operand="A">
    <ConnectionPointIn><Connection refConnectionPointOutId="1"/></ConnectionPointIn>
    <ConnectionPointOut connectionPointOutId="2"/>
  </LdObject>
  <LdObject xsi:type="Coil" latch="set" operand="B">
    <ConnectionPointIn><Connection refConnectionPointOutId="2"/></ConnectionPointIn>
    <ConnectionPointOut connectionPointOutId="3"/>
  </LdObject>
  <LdObject xsi:type="RightPowerRail">
    <ConnectionPointIn><Connection refConnectionPointOutId="3"/></ConnectionPointIn>
  </LdObject>
</Rung>
```

Regole usate:
- **Serie:** l'ingresso dell'elemento punta all'uscita del precedente.
- **OR:** l'elemento dopo il parallelo ha più `Connection` nello stesso `ConnectionPointIn`.
- **Rami dalla sinistra:** ogni ramo che parte dalla barra ha il suo `ConnectionPointOut` nel `LeftPowerRail`.
- **Più uscite:** più bobine puntano alla stessa uscita. Il `RightPowerRail` ha un `ConnectionPointIn` per ogni bobina.

Blocchi (`FbdObject xsi:type="Block"`). Ogni pin ha nell'`AddData` il suo `smcext:ConnectionPointInOrder` o `smcext:ConnectionPointOutOrder`. Le costanti e le variabili entrano con `DataSource identifier="..."`, le uscite vanno in `DataSink identifier="..."`; un'uscita non usata va in un `DataSink` con `identifier=""`.

| Blocco | Ingressi | Uscite |
|---|---|---|
| `TON` con `instanceName` | `In` (potenza), `PT` | `Q` (alla barra destra), `ET` |
| `MOVE` | `EN` (potenza), `In` | `ENO` (alla barra destra), `Out` |
| `Inc` | `EN` (potenza), InOut `InOut` | `ENO`, `""`, uscita di `InOut` |
| `>=`, `<>`, `<` | `EN` (potenza), `In1`, `In2` | `""` (prosegue la potenza) |

Letterali: `T#500ms`, `UINT#2`, `WORD#16#0`.

Altri dettagli provati:
- AT built-in: `<Address address="BuiltInIO://cpu/#0/Input_Bit_00"/>`, stessa forma per `Output_Bit_00`.
- Commenti di variabile: `Documentation xsi:type="SimpleText"`; per elemento `smcext:ElementComment element="bit[3]"`.
- Nomi di sezione: sono stati rinominati senza `_` iniziale (`S000_Generali`), non è stato provato se il `_` viene accettato.
- Ritenzione: si dichiara con il gruppo `GlobalVars retain="true"`.

## Conversione da CX-Programmer

- **Importatore Omron non disponibile.** `Project` > `Converter` > `CS/CJ Series Import` esiste nel template, ma la DLL lo registra solo con un controllo di attivazione e l'impostazione `CJCON` = `TRUE`. È un blocco del costruttore: non forzarlo, si chiede a Omron.
- **Leggere il `.cxp`:** è il `.cxt` compresso con PKWARE implode (header `00 06`). Decomprimi una copia con `scripts/cxp_explode.py`: il `.cxt` è testo, con simboli, mnemonico per rete e valori DM nel blocco `Memory`.
- **Help istruzioni:** `C:\Program Files (x86)\OMRON\CX-One\CX-Programmer\PLCRefCP1E.chm` e simili. Si decompilano con `hh.exe -decompile`, lanciato dalla cartella del file e con nome breve.

| CX-Programmer | Sysmac Studio |
|---|---|
| `@LD`, `@AND`, `@OR` | contatto `edge="rising"` |
| `SET`, `RSET` | bobina `latch="set"` / `latch="reset"` |
| `TIMHX(551)` | `TON`; preset in unità di 10 ms, quindi `PT` = valore × 10 ms |
| `MOV(021)` | `MOVE` |
| `++(590)` | `Inc` |
| word usata anche a bit | `Un_WordBit`: `Var.W`, `Var.bit[n]` |
| `P_First_Cycle` | `P_First_RunMode` |
| `NOP`, `END` | eliminati |

Aperto: `@ANDNOT` non è definito chiaramente nell'help. In 00380 è stato letto come "vero tranne nello scan di salita", con una variabile dello scan precedente: da confermare sulla macchina.

I preset salvati nel progetto possono differire da quelli nel PLC reale: chiedi a Matteo di rileggerli.
