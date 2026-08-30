# Vault ↔ Memory Index

> **Connects the canonical git-tracked vault, the agent memory system, and the retired mirror.**

## Canonical Vault (Authoritative)
**Location:** `olp_xdv_agent/olp_xdv/docs/obsidian-vault/` (git-tracked)
**Per Architect directive 2026-08-16** — this is the single source of truth.

### Core Notes (all interconnected via `[[wikilinks]]`)
- `[[OLP XDV.md]]` — Entry point, read first every session
- `[[Rules.md]]` — All HRs/IDs as coded + doc-vs-code disagreements
- `[[Decisions Log.md]]` — Dated Architect directives (backfilled + 4× 11-Aug-2026)
- `[[Protected Constants.md]]` — Off-limits: `ARCHITECT_SIGNOFF`, CLV gate, capital deployment
- `[[Agents.md]]` — 16 project agents (7 chusri + 9 plugin) with model/tools
- `[[Architecture.md]]` — Pipeline: SCAN → trigger → publish, CLV loop, admin dash
- `[[Open Questions.md]]` — Unresolved items needing explicit Architect answer
- `[[Loops.md]]` — Recurring pipeline loops
- `[[README.md]]` — Vault overview
- `[[API Keys.md]]` — Credential reference (sanitized, real values in .env only)
- `[[OLP_XDV_Framework_Index.md]]` — Navigation index with repo paths
- `[[Vault-Memory-Index.md]]` — This file
- `[[STATE.md]]` — Daily retrospective audit: fixture verification, outcome audit, knowledge integration

## Agent Memory System (Persistent Across Sessions)
**Location:** `.claude/projects/C--Users-Motunrayo-omniroute-test/memory/`

### Memory Index
- `[[MEMORY.md]]` — Master index (this file links to all memories below)

### Individual Memories
- `[[olp-xdv-agent.md]]` — OLP XDV agent: Telegram bot/daemon + web wiring, publish gate, commit conventions
- `[[safe-move-protocol.md]]` — Default opening move: check git status/log first
- `[[git-commit-sweeps-staged.md]]` — `git commit` sweeps other session's staged files
- `[[data-quality-monitor.md]]` — Season state, extra-league coverage, mypy/ruff gate
- `[[booking-sportybet.md]]` — Booking modules: requests client, Playwright cache, bridge
- `[[save-all-conversations.md]]` — Stop hook archives transcripts to memory/conversations/
- `[[commit-always.md]]` — Commit every session's work; never leave tree dirty
- `[[everything-claude-code.md]]` — Plugin in OLP XDV .claude/; use agents/skills/commands/rules
- `[[awesome-design-md.md]]` — Design-token library (73 brands); pitch-night palette in proto.css
- `[[sports-data-skills.md]]` — machina-sports skills (4 skills in .claude/skills/)
- `[[claude-code-action.md]]` — anthropics/claude-code-action cloned at workspace root
- `[[always-check-date.md]]` — Always verify the real current date at session start / before date-sensitive work

## Retired Mirror (Deprecated 2026-08-18)
**Location:** `Documents/OLP_XDV_Vault/` — **NOT authoritative, non-git, READ-ONLY**
**Status:** Retired and marked deprecated. All unique content migrated to canonical vault.

### Migration Complete (2026-08-18)
- `Vault-Memory-Index.md` → migrated to canonical vault (this file)
- `OLP_XDV_Framework_Index.md` → migrated to canonical vault
- `API Keys.md` → migrated to canonical vault (sanitized)
- `Loops.md` → already existed in canonical vault

### Files Remaining in Mirror (read-only reference)
- `Pipeline Runs/` — historical pipeline artifacts
- `.obsidian/` — Obsidian workspace config
- `.trash/` — Obsidian trash
- All `.md` files are now read-only (Windows `attrib +R` applied)

### DEPRECATED_NOTICE.md
Created in mirror root with full deprecation notice and migration log.

## Quick Navigation
| Target | Link |
|--------|------|
| Canonical vault root | `file:///C:/Users/Motunrayo/omniroute%20test/olp_xdv_agent/olp_xdv/docs/obsidian-vault/` |
| Agent memory root | `file:///C:/Users/Motunrayo/.claude/projects/C--Users-Motunrayo-omniroute-test/memory/` |
| OLP XDV repo root | `file:///C:/Users/Motunrayo/omniroute%20test/olp_xdv_agent/olp_xdv/` |
| Retired mirror (read-only) | `file:///C:/Users/Motunrayo/Documents/OLP_XDV_Vault/` |

## Two-Way Sync Status
**Active:** `vault-memory-sync.js` (bidirectional sync between canonical vault ↔ agent memory)
**Configured:** SessionStart/SessionEnd hooks enforce HR54 compliance on both stores