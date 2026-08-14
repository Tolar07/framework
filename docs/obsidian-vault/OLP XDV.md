# OLP XDV — Vault Home

> **Read this first — it is the entry point for every session.** The notes
> below are the persistent memory for the OLP XDV football-betting calibration
> framework (`olp_xdv_agent/olp_xdv`), pulled from the **actual code** (verified
> 2026-08-11, refreshed 2026-08-13). If you only read one thing, read this page.

## What OLP XDV is
A **Phase-3 live** football-betting calibration framework (paper→live transition
ratified 2026-08-11). A daily pipeline scans **61 whitelisted leagues** from the
dynamic registry (`config/leagues.json`, aggressive European expansion ratified
2026-08-12), fits
Dixon-Coles + Elo + xG + bookmaker engines into one consensus, builds a board,
produces a **today-only** bet (Acca A + split accas + singles) priced on
**SportyBet's own line** with **booking codes**, logs **paper legs with CLV**, and
delivers to Telegram + a two-tier web dashboard. It **never places a bet** — the
Architect turns a booking code into money. Statistical gate: **12/30 legs with
CLV, mean CLV −1.631% (NOT met)** — the live publish runs on the Architect's
`ARCHITECT_SIGNOFF` override, side-by-side with paper until CLV turns positive.

## Core notes
- **[[Rules.md]]** — every HR (hard rule) and ID (protocol) as coded: number,
  status, and the file/function that implements it. Also the standing
  (un-numbered) rules and the doc-vs-code disagreements.
- **[[Decisions Log.md]]** — the dated record of every explicit Architect
  directive, backfilled + the four 11-Aug-2026 directives (softness cancelled,
  ID405 away-win override, API key priority, per-fixture market selection) —
  each verified in code.
- **[[Protected Constants.md]]** — things no agent may edit or self-approve:
  `ARCHITECT_SIGNOFF`, the CLV/legs publish gate, client-publish gating, capital
  deployment.
- **[[Agents.md]]** — the full roster (16 project agents: 7 chusri + 9 plugin)
  with model/tools/function and the resolved overlaps.
- **[[Architecture.md]]** — the pipeline end to end: SCAN → trigger production →
  publish, the CLV loop, the admin dashboard, Telegram/client output.
- **[[Open Questions.md]]** — unresolved items needing an explicit Architect
  answer before anything is assumed (calibration-log scope, per-market price
  coverage, quota timing, and more).

## How to start a session
1. Read this page.
2. **Rules.md** for what's allowed; **Protected Constants.md** for what's off-limits.
3. **Decisions Log.md** for what the Architect decided; **Open Questions.md** for
   what is still undecided.
4. **Architecture.md** for how it fits together; **Agents.md** for who to call.
5. Update **Open Questions.md** (new uncertainties) and **Decisions Log.md** (new
   directives) as work proceeds — these two are the living records.

## Standing reminders (from the code, 2026-08-11)
- **Odds API quota = 1/500** — prices for non-deploy leagues are `NO DATA — PENDING` (HR35).
- **HR35 (no fabrication)** is the most-cited rule in the codebase.
- **RATIFICATIONS.md is append-only** (HR33); a go-live entry was retroactively
  appended 2026-08-11 (commit `76216e0`) — the config.py comment had claimed it
  without it existing.
- Vault folder: `docs/obsidian-vault/` in the repo (moved here + committed
  2026-08-11). A copy also lives at `Documents/OLP_XDV_Vault` for Obsidian to
  open. Built by Claude Code directly (Obsidian MCP was not connected — the
  notes are plain markdown and work identically).
