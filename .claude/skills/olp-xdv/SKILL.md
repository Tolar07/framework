---
name: olp-xdv
description: |
  OLP XDV read-only query surface over the live framework's saved records: the latest board, the picks ledger (every pick and every rated fixture, graded), the scorecard and model check, the CLV log / Phase 3 gate, and the league whitelist.

  Use when: the Architect asks "how are we doing", "show the board", "what did we predict for <team>", "what were yesterday's picks and results", the CLV / Phase 3 gate status, or which leagues are covered.
  Don't use when: the user asks to RUN the pipeline, produce a new board, fetch today's fixtures or odds (that needs a fetch in this session, HR59), or place/record bets — this skill only reads saved records.
metadata:
  type: project
---

OLP XDV is the Architect's football betting framework at Phase 3 (live
capital, Architect-deployed). The framework builds boards and booking codes;
it never places a stake.

## Read-only contract
- Never run `run_daily.py` or any fetch from this skill; never place bets.
- Every answer comes from a saved record and names its date. A record that
  isn't there reads **NO DATA — PENDING** (HR35) — never a number from memory.
- A saved board is a record of an earlier fetch, not today's live data. If the
  Architect wants today's fixtures or prices, say so and run the fetch
  (`python run_daily.py --no-send --target-date <day>`), per HR59.

## Commands

`python scripts/olp_query.py <command> [arg] [--json]`, from the repo root.

| Command | Answers |
|---|---|
| `status` | Phase, CLV log / Phase 3 gate (legs with CLV, mean CLV, requirement), latest board and ledger dates |
| `board [YYYY-MM-DD]` | The saved canonical board (latest if no date) |
| `picks [YYYY-MM-DD]` | That day's picks with price, chance, certainty, booking code and result |
| `scorecard [--days N]` | W-L, hit rate, profit at 1 unit, by tier and certainty, slips landed, calibration, model check, CLV |
| `lookup <team>` | Every pick and rated fixture involving the team, with results |
| `leagues` | Whitelisted leagues and deploy eligibility |

Records live in `output/boards/board_<date>.txt`, `output/picks/picks_<date>.json`
and `clv/clv_log.json`; `engine/picks_ledger.py` explains the ledger fields.
