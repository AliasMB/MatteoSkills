# La sorgente VM

ActivityWatch gira anche dentro la macchina virtuale `SiemensPC` (VMware
Workstation, quella con TIA Portal), installato il **24/08/2026**. Il suo
database sta dentro la VM, quindi va portato fuori a mano.

## La copia mensile

Serve una volta al mese, **prima** di generare il consuntivo. Dentro la VM:

1. Chiudi ActivityWatch (icona nel tray → Quit). Il database è SQLite in
   journal mode `delete`: una copia presa a server acceso può pescare una
   transazione a metà.
2. Copia
   `%LOCALAPPDATA%\activitywatch\activitywatch\aw-server\peewee-sqlite.v2.db`
   in `ActivityLog\vm_data\`, senza rinominarlo. È l'unico file che serve:
   niente `-wal` né `-shm`, e `device_id` / `aw-server.toml` non contengono
   dati.
3. Riavvia ActivityWatch nella VM.

La cartella `vm_data/` sulla macchina fisica è condivisa nella VM come shared
folder VMware, quindi la copia è un trascinamento. **Non puntare aw-server a
scrivere il suo database live dentro la shared folder**: HGFS non garantisce il
locking che SQLite si aspetta, e il rischio è corrompere il file.

## Cosa controllare prima di consegnare

Il database è cumulativo: contiene tutta la storia, non solo il mese. Quindi
una copia basta per rigenerare un mese passato solo se gli eventi
ne coprono effettivamente il periodo. La copia recente, da sola, non
garantisce questa copertura.

Ma se la copia è **più vecchia** del periodo richiesto, le ore dentro la VM di
quei giorni escono senza dettaglio e ricadono sul contesto. Lo script avvisa su
stderr solo quando il file manca del tutto — che sia vecchio non può saperlo.
La data del file non prova la copertura: anche una copia di oggi può
contenere eventi vecchi. Verifica gli estremi degli eventi del bucket
finestra, considerando `timestamp + duration` per la fine, e i buchi nel
periodo richiesto. L'AFK del guest non certifica la copertura delle finestre.
Segnala l'ultimo giorno eventualmente parziale e le date senza dettaglio VM
**prima** di consegnare; in quelle fasce opera il contesto host.

Verifica rapida del contenuto:

```bash
python -c "
import sqlite3
c=sqlite3.connect('file:vm_data/peewee-sqlite.v2.db?mode=ro',uri=True)
for r in c.execute('select bucket_id,count(*),min(timestamp),max(timestamp) from eventmodel group by bucket_id'): print(r)
for r in c.execute('select bucket_id,timestamp,duration from eventmodel order by timestamp desc limit 5'): print(r)
c.close()
"
```

## Impostazioni dentro la VM

Le categorie sono quelle definite da Matteo nella UI: `settings.json` è stato
copiato dall'host alla VM il 21/09/2026, quindi le due istanze categorizzano
allo stesso modo. Se un giorno divergono, la copia va rifatta nella stessa
direzione (host → VM), mai al contrario.

Entrambe le istanze sono ActivityWatch **v0.13.2**.

`Siemens.Automation.Portal.exe` non è coperto da nessuna categoria e risulta
`Non categorizzato`. È un'informazione, non un buco da tappare: le categorie le
decide Matteo dalla UI, non si modifica `settings.json` a mano.

## Come entra nel calcolo

Il meccanismo è `innesta_vm()` in `aw_report.py`. Gli eventi dell'host che
corrispondono al `pattern` vengono sostituiti dagli eventi che la VM ha
registrato nello stesso intervallo, ritagliati sui suoi bordi.

Tre vincoli, tutti nati da errori veri trovati in fase di verifica:

- **La cornice della giornata si misura sull'host**, non sui dati sostituiti.
  La VM produce eventi molto più fitti (798 contro 99, il 10/09) e la
  frammentazione fa cadere i blocchi di inizio giornata sotto la soglia dei due
  minuti: misurando lì, il 10/09 cominciava alle 08:33 invece che alle 08:25.
- **I buchi tornano all'host.** Dove la VM copre solo in parte un intervallo
  l'evento originale riempie il resto, altrimenti la giornata si accorcia
  (10/09: 7h31 → 7h17).
- **Il titolo dell'host resta in coda** a quello della VM
  (`[VM] Claude · Siemens - VMware Workstation`). Senza, le finestre mute del
  guest perdono anche l'aggancio di contesto: il 31/08 i 72 minuti di
  `claude.exe` dentro la VM uscivano dalla commessa.

Il marcatore `[VM]` ha la forma `[..]` e viene rimosso da `pulisci()` prima che
si cerchino i codici commessa, quindi non interferisce col riconoscimento.
