# MatteoSkills — regole per chi modifica questa repo

Questa nota vale solo per lavorare sulla repo: non fa parte di nessun plugin e non viene installata.

- **Versioning obbligatorio:** ogni modifica a un file dentro `plugins/<nome>/` richiede di alzare `version` in `plugins/<nome>/.claude-plugin/plugin.json`, nello stesso commit. Semver: patch = correzione/testo, minor = contenuto o skill nuova, major = rinomina/rimozione di skill o plugin. Senza il bump gli utenti non ricevono l'aggiornamento.
- La versione sta solo in `plugin.json`, non in `.claude-plugin/marketplace.json`.
- Prima del commit: `claude plugin validate .` deve passare.
- Percorsi a file della skill: usa `${CLAUDE_SKILL_DIR}`, mai percorsi assoluti.
- Descrizioni delle skill: corte, prima cosa fa poi "Usa quando…" con le parole che Matteo usa davvero.
