---
name: tia-portal-scl-blocks
description: "Crea, modifica e compila FB, FC e DB in SCL per Siemens TIA Portal, anche safety (F-Program). Usa per qualsiasi codice PLC Siemens."
---

# TIA Portal SCL Blocks Creation Guide

## Overview
This skill guides the correct structure, variable declarations, and compiler constraints for creating Siemens S7-1200/S7-1500 blocks (FBs, FCs, DBs) in Structured Text (SCL) for TIA Portal.

---

## 1. Block Interface Structure & Keywords

TIA Portal SCL has strict rules for block declarations. Variable sections must be declared in the block header (before `BEGIN`) and closed with `END_VAR`.

### Correct Variable Keywords:
*   `VAR_INPUT` ... `END_VAR` (Input parameters)
*   `VAR_OUTPUT` ... `END_VAR` (Output parameters)
*   `VAR` ... `END_VAR` (Static variables - FBs only)
*   `VAR_TEMP` ... `END_VAR` (Temporary variables)
*   `VAR CONSTANT` ... `END_VAR` (Local constants)

> [!IMPORTANT]
> **Syntax Rule for Constants:**
> 1. Use **`VAR CONSTANT`** with a space. Writing `VAR_CONSTANT` with an underscore will fail compilation!
> 2. Always close the constant block with **`END_VAR`**. Never use `END_CONSTANT`!
> If the constant block syntax fails, TIA Portal will reject the entire block interface, leaving all block parameters blank.

### Example Template (FB):
```scl
FUNCTION_BLOCK "FB_MyCustomBlock"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
   VAR_INPUT
      i_Enable : Bool;
   END_VAR
   VAR_OUTPUT
      o_Status : Bool;
   END_VAR
   VAR
      stat_State : Int := 0;
   END_VAR
   VAR_TEMP
      temp_Trigger : Bool;
   END_VAR
   VAR CONSTANT
      STATE_IDLE : Int := 0;
      STATE_RUNNING : Int := 10;
   END_VAR

BEGIN
   // Block code here...
END_FUNCTION_BLOCK
```

---

## 2. Standard Global DB Declaration

To create a global DB via SCL source code:

```scl
DATA_BLOCK "DB_MyGlobalData"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
NON_RETAIN
   VAR 
      MyVariable1 : Bool; // Comment
      MyVariable2 : Int;  // Comment
   END_VAR
BEGIN
END_DATA_BLOCK
```

---

## 3. Standard-Safety DB Bridge Rules (F-Program Constraints)

When exchanging data between standard SCL logic and failsafe F-Programs (F-FBD/F-LAD):

> [!WARNING]
> **Strict Siemens Safety Compilation Rule:**
> In the F-Program, any single variable in a standard DB (e.g., `"DB_SafetyBridge".MyVar`) can be **either read or written, but never both**. 
> Failing this rule triggers a `Consistency Check` error.

### The Solution:
1.  **For Outputs from Safety**: Write F-program logic to local F-Static variables (e.g., `#statMyVar`). Assign this local variable to the standard DB tag in a parallel/terminal write assignment.
2.  **For Inputs to Safety**: Read from the local F-Static variable (`#statMyVar`) instead of the standard DB tag for all internal logic networks.

---

## Common Mistakes & Verification Checks:
*   ❌ **Writing `VAR_CONSTANT` instead of `VAR CONSTANT` (with space)**: TIA Portal SCL strictly requires a space. An underscore will break block interface compilation.
*   ❌ **Writing `END_CONSTANT` instead of `END_VAR`**: Always close the constant block with `END_VAR`. Writing `END_CONSTANT` will cause the compiler to flag the `BEGIN` keyword as invalid and fail.
*   ❌ **Reading and writing standard tags in Safety**: Standard DB tags cannot be both read and written within the failsafe program. Use local F-Static variables (`#stat...`) instead.

> [!IMPORTANT]
> **Check before saving:**
> Always verify that there are no occurrences of the word `END_CONSTANT` or `VAR_CONSTANT` (with underscore) in your generated SCL files before writing them!

---

## 4. TIA Portal External Source File Workflow (Generazione Blocchi da File Sorgente Esterno)

> [!IMPORTANT]
> **Workflow di Importazione in TIA Portal:**
> Su TIA Portal, i blocchi SCL vengono importati tramite **"Sorgenti esterne" -> "Aggiungi nuovo file sorgente esterno"** (Add new external source file) e compilati cliccando su **"Genera blocchi da sorgente"**.
> 
> **Regola Operativa per l'LLM:**
> Ogni volta che si crea o aggiorna un blocco SCL (FB, FC, DB), l'LLM DEVE:
> 1. Salvare il file `.scl` stand-alone **ESCLUSIVAMENTE** all'interno della cartella dedicata `siemens_blocks/` nella root di progetto (es. `<workspace_root>/siemens_blocks/<NomeBlocco>.scl`).
> 2. NON disperdere file `.scl` nella root del progetto o nelle sottocartelle VCI.
> 3. Fornire all'utente il link cliccabile al file in `siemens_blocks/` affinché l'utente possa copiarlo o importarlo a mano in TIA.


