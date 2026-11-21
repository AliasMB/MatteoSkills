---
name: twincat-st
description: "Regole ST/ExST e procedura di verifica per Beckhoff TwinCAT 3. Usa per scrivere, nominare o correggere codice, compilare un PLC o eseguire test su UmRT, con ADS o TF1140 oppure sviluppare e collaudare una HMI TwinCAT TE2000."
---

# TwinCAT 3 — ST/ExST e HMI

Leggi il riferimento adatto prima di scrivere codice o avviare un collaudo. I file sono in `${CLAUDE_SKILL_DIR}/references/`.

| Quando | Leggi |
|---|---|
| Crei o rinomini variabili, FB, DUT, funzioni, metodi, proprietà, interfacce (sempre, prima di dare un nome) | `naming-conventions.md` |
| Tipi, array, STRUCT, ENUM, POINTER, REFERENCE, NEW/DELETE, allineamento `pack_mode` | `datatypes-memory.md` |
| Operatori, precedenze, IF/CASE/FOR/WHILE, MOD/SHL/ADR/BITADR, parole riservate IEC | `syntax-control-flow.md` |
| Proprietà GET/SET, metodi, FB_init/FB_reinit/FB_exit, state machine, pragma, PlcTaskSystemInfo | `advanced-patterns.md` |
| Errori di build, warning del compilatore, `CheckPlcSyntaxAsync` fallito | `troubleshooting.md` |
| Compilazione PLC, test su UmRT o collaudo tramite ADS o TF1140 | `build-and-test.md` |
| Sviluppo e collaudo di TwinCAT HMI TE2000 | `hmi-test.md` |
