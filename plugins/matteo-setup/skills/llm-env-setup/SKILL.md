---
name: llm-env-setup
description: "Installa e configura globalmente gli strumenti e le skill di base per lo sviluppo con LLM (doomer-agent, Agent-Reach, agent-browser, mattpocock/skills). Usa quando Matteo chiede setup ambiente LLM, preparazione nuovo PC/agente, installazione tool di base o nomina questi repository."
---

# Setup rapido ambiente di sviluppo LLM

Configura in un solo passaggio i 4 strumenti standard di Matteo (**doomer-agent**, **Agent-Reach**, **agent-browser**, **mattpocock/skills**) usando gli installer globali ufficiali, senza lasciare clone `git` locali.

## 1. Riconosci l'ambiente attivo

Prima di eseguire qualsiasi comando, identifica su quale piattaforma stai girando (contesto di sistema, variabili d'ambiente o percorso delle skill caricate) e imposta `<AGENT_ID>` e `<GLOBAL_SKILLS_DIR>`:

| Ambiente | Segnali di riconoscimento | `<AGENT_ID>` (`npx skills -a`) | `<GLOBAL_SKILLS_DIR>` |
|---|---|---|---|
| **Claude** (Claude Code) | Variabili `CLAUDE_CODE*` o `CLAUDE_SKILL_DIR` in `~/.claude` | `claude-code` | `~/.claude/skills` |
| **Google** (Antigravity / Gemini) | `App Data Directory` in `.gemini\antigravity` o skill in `~/.gemini/config/skills` | `antigravity` | `~/.gemini/config/skills` |
| **ChatGPT** (OpenAI Codex) | Contesto Codex CLI/App o variabili `CODEX_*` | `codex` | `~/.agents/skills` |

Se Matteo chiede il setup per **tutti** gli ambienti installati sulla macchina, passa tutti i flag contemporaneamente (`-a claude-code -a antigravity -a codex`).

## 2. Regole vincolanti (Errori comuni da evitare)

| Errore / Scorciatoia | Realtà e regola obbligatoria |
|---|---|
| `git clone` dei 4 repository | **Vietato.** Usa solo installer globali (`npx skills`, `uv tool`, `npm -g`, `claude plugin`). |
| `uv tool install agent-reach` o `pip install agent-reach` | **Vietato.** Il pacchetto `agent-reach` su PyPI **non** è il progetto di Panniantong. Usa **solo** l'URL `.zip` della release GitHub ufficiale. |
| `npx skills add` senza `--copy` su Windows | **Vietato.** Senza Developer Mode o privilegi admin i symlink falliscono su Windows. Passa sempre `--copy`. |
| Installare `mattpocock/skills` su Claude Code sia come plugin sia con `npx skills` | **Vietato.** Duplica tutte le skill. Su Claude Code usa `claude plugin install`; usa `npx skills` solo su Antigravity/Codex (o come fallback se il marketplace non risponde). |

## 3. Procedura di installazione

Esegui i 4 blocchi in ordine.

### A. `jnh12/doomer-agent` (Reel/contenuti salvati → skill riutilizzabili)

```powershell
npx -y skills@latest add jnh12/doomer-agent -g -a <AGENT_ID> --copy -y
```

*Fallback se la CLI `skills` non rileva il file:* scarica direttamente `https://raw.githubusercontent.com/jnh12/doomer-agent/main/SKILL.md` in `<GLOBAL_SKILLS_DIR>/doomer-agent/SKILL.md`.

### B. `Panniantong/Agent-Reach` (Accesso web/social zero-API per agenti)

1. Verifica `uv --version`. Se manca, installalo:
   - **Windows:** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - **Linux/macOS:** `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Installa la CLI dalla release GitHub ufficiale, inizializza i canali e registra la skill:

```powershell
uv tool install https://github.com/Panniantong/Agent-Reach/releases/latest/download/agent-reach.zip
agent-reach setup
npx -y skills@latest add Panniantong/Agent-Reach@agent-reach -g -a <AGENT_ID> --copy -y
```

*(Se `agent-reach` non è nel PATH subito dopo `uv tool install`, esegui `uv tool update-shell` o usa il binario in `~/.local/bin/agent-reach`).*

### C. `vercel-labs/agent-browser` (CLI browser automation token-efficient)

Richiede Node.js. Installa la CLI globale, scarica il browser companion e registra la skill:

```powershell
npm install -g agent-browser
agent-browser install
npx -y skills@latest add vercel-labs/agent-browser -g -a <AGENT_ID> --copy -y
```

### D. `mattpocock/skills` (Workflow SDLC: `grill-me`, `tdd`, `write-a-prd`, ecc.)

- **Se `<AGENT_ID>` è `claude-code`** (plugin gestito con aggiornamenti automatici):
  ```powershell
  claude plugin install mattpocock-skills@claude-plugins-official
  ```
- **Se `<AGENT_ID>` è `antigravity` o `codex`** (oppure se `claude plugin` non è disponibile):
  ```powershell
  npx -y skills@latest add mattpocock/skills -g -a <AGENT_ID> --all --copy -y
  ```

## 4. Verifica finale obbligatoria

Non dichiarare il setup completato senza aver eseguito e mostrato l'esito di:

```powershell
npx -y skills@latest list -g
agent-reach doctor
agent-browser --version
```

Chiudi con una tabella riepilogativa: **Ambiente rilevato**, **Strumento**, **Metodo usato**, **Esito verifica (`OK` / `ERRORE`)**.
