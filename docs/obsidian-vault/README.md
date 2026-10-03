# OLP XDV — Obsidian Memory Vault

This folder is an Obsidian vault for the OLP XDV project's persistent memory.

**Status: POPULATED 2026-08-11.** The Obsidian MCP was not connected, so Claude
Code wrote the notes directly (a vault is just markdown — Obsidian reads them
identically). Start at [[OLP XDV.md]]:

- `OLP XDV.md` — entry point (links to everything below)
- `Rules.md` — every HR/ID, status, implementing file
- `Decisions Log.md` — dated Architect directives (backfilled + 11-Aug-2026)
- `Protected Constants.md` — things no agent may self-approve
- `Agents.md` — full agent roster (7 chusri + 9 plugin)
- `Architecture.md` — pipeline end to end
- `Open Questions.md` — unresolved items needing an Architect answer
- `Loops.md` — recurring pipeline loops

**To use:** Obsidian → "Open folder as vault" → select this folder.

---

## External Connections

### Agent Memory System (Persistent Across Sessions)
**Location:** `.claude/projects/C--Users-Motunrayo-omniroute-test/memory/`

- `MEMORY.md` — Master index linking all memories
- Individual memories: `olp-xdv-agent.md`, `safe-move-protocol.md`, `git-commit-sweeps-staged.md`, `data-quality-monitor.md`, `booking-sportybet.md`, `save-all-conversations.md`, `commit-always.md`, `everything-claude-code.md`, `awesome-design-md.md`, `sports-data-skills.md`, `claude-code-action.md`

### Deprecated Mirror (Drifted, Non-Git)
**Location:** `Documents/OLP_XDV_Vault/` — **NOT authoritative**

Per Architect directive 2026-08-16, the canonical vault is this git-tracked folder.
The mirror at `Documents/OLP_XDV_Vault` is deprecated and may contain stale/outdated content.
See `Documents/OLP_XDV_Vault/Vault-Memory-Index.md` for a cross-reference.