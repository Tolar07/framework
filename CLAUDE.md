# CLAUDE.md — OLP XDV Agent Workspace

> Single source of truth for Claude Code sessions in this workspace. Read at session start.

**OLP XDV Agent** — Telegram bot/daemon for sports data collection, odds processing and automated
publishing with a CLV (Closing Line Value) feedback loop.

- OLP XDV repo (submodule, GitHub `Tolar07/framework`): `olp_xdv_agent/olp_xdv/`
- Canonical vault (git-tracked, authoritative): `olp_xdv_agent/olp_xdv/docs/obsidian-vault/` — start with `OLP XDV.md`
- Agent memory: `.claude/projects/C--Users-Motunrayo-omniroute-test/memory/` (index: `MEMORY.md`)
- `Documents/OLP_XDV_Vault/` is a retired, read-only mirror (HR57). Never treat it as authoritative.

---

## Token budget (Architect 2026-10-19 — applies to every session)

Every tool call re-sends the whole conversation, so a long session costs more with each step. On
2026-10-19 one reused session had cost $483 and scheduled tasks were failing with "usage limit reached".

1. **One session per job.** Don't keep one session running for days. When the topic changes, `/clear`
   (or `/compact` if the thread matters). Past ~200k tokens of context, finish up and suggest a fresh session.
2. **Scheduled tasks start a fresh session on every run** (`create_new_session_on_fire`) and use
   `claude-sonnet-5-5`, unless the Architect asks otherwise. Don't bind a scheduled task to a persistent session.
3. **Match the effort to the job.** Routine checks: Sonnet at medium or low effort. Opus and high/xhigh/max only for real design work.
4. **Don't re-do what GitHub already does.** Boards go out by themselves (`daily.yml` cron + `clock.yml` +
   `watchdog.yml`). Claude only steps in when a run failed or a board is missing.
5. **Use as few subagents as you can.** Each subagent starts cold and re-reads everything. Use one only to keep a
   huge output out of context, or when the Architect asks for one.
6. **Keep tool output small.** Use `head`, `--short`, `-L 5`, `grep -c` and filters. Don't dump whole logs,
   session lists or JSON. Read the parts of a file you need.
7. **Message other sessions narrowly.** Contact the one session that owns the topic, not every session
   (see memory `ask-all-sessions-first`).
8. **Background jobs on the PC go through `scripts/llm-run.ps1`**, never a bare `claude.exe -p`. It runs text jobs on
   OmniRoute's free models (`auto/pro-coding`) and falls back to Sonnet if OmniRoute fails. Browser (`-Chrome`) jobs go
   straight to Sonnet, because Claude in Chrome needs the claude.ai login. Every run is logged to `%USERPROFILE%\llm-router.log`.

---

## Critical Rules (full list in vault `Rules.md`)

| HR | Description |
|----|-------------|
| **HR54** | Vault ↔ Memory sync on SessionStart/SessionEnd |
| **HR57** | Mirror retired — canonical vault only |
| **HR58** | Vault is git-tracked single source of truth |
| **HR59** | Sync hardening — bidirectional enforcement |

**Protected constants (never modify without Architect sign-off):** `ARCHITECT_SIGNOFF`, the CLV gate,
capital deployment. See vault `Protected Constants.md`.

**Protected files** — any change (including Task Observer staged updates) needs manual line-by-line review:
`olp_xdv_agent/olp_xdv/bets/booking_tracker.py`, `olp_xdv_agent/olp_xdv/variant_selection.py`, the odds
tolerance check (`booking/verify_external_code.py` and `Rules.md`), `automaton/constitution.md`.

---

## Workflows

**Session start:** read `MEMORY.md` and the vault's `OLP XDV.md`; `node scripts/vault-memory-sync.js`;
`git status --short | head -20 && git log --oneline -5`.

**Session end:** run the vault-memory sync, commit your own changes, update `docs/STATE.md`.

**Making changes:** read the file before editing; keep changes atomic and scoped; update vault notes when
architecture or decisions change; run the sync after vault edits. `git commit` sweeps other sessions' staged
files — prefer `git commit --only <paths>` (memory `git-commit-sweeps-staged`).

```bash
node scripts/vault-memory-sync.js                       # sync vault <-> memory
cd olp_xdv_agent/olp_xdv && python -m olp_xdv           # run the agent
cd olp_xdv_agent/olp_xdv && pytest                      # tests
```

**Environment:** Python 3.11+ (venv `olp_xdv_agent/olp_xdv/.venv`), Node 20+, Playwright installed.
Real credentials live in `.env` only — never commit them.

**Task Observer** (`.claude/skills/task-observer/`): project-level, staging-only. It logs to
`skill-observations/log.md` and stages to `skill-updates/`, and never auto-applies. Invoke it for
substantive multi-step work, not for quick checks.

**Supervisor agent:** `olp-xdv-supervisor` coordinates multi-session state via `docs/STATE.md`.

*Last updated: 2026-10-19*
