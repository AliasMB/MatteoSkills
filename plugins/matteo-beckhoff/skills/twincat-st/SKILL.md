---
name: twincat-st
description: "Regole Beckhoff TwinCAT 3 in ST/ExST: naming (notazione ungherese), tipi di dato e memoria, sintassi, pattern avanzati (metodi, proprietà, FB_init), errori di compilazione. Usa per scrivere, nominare o correggere codice TwinCAT."
---

# TwinCAT 3 — regole ST/ExST

Leggi il riferimento adatto PRIMA di scrivere o correggere codice. I file sono in `${CLAUDE_SKILL_DIR}/references/`.

| Quando | Leggi |
|---|---|
| Crei o rinomini variabili, FB, DUT, funzioni, metodi, proprietà, interfacce (sempre, prima di dare un nome) | `naming-conventions.md` |
| Tipi, array, STRUCT, ENUM, POINTER, REFERENCE, NEW/DELETE, allineamento `pack_mode` | `datatypes-memory.md` |
| Operatori, precedenze, IF/CASE/FOR/WHILE, MOD/SHL/ADR/BITADR, parole riservate IEC | `syntax-control-flow.md` |
| Proprietà GET/SET, metodi, FB_init/FB_reinit/FB_exit, state machine, pragma, PlcTaskSystemInfo | `advanced-patterns.md` |
| Errori di build, warning del compilatore, `CheckPlcSyntaxAsync` fallito | `troubleshooting.md` |
