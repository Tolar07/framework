# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

## What this is

**OLP XDV** — a football match-modelling framework that produces a daily
*paper* board of model probabilities and breakeven trigger prices, and logs
closing-line value (CLV) on every leg. Python 3.12, no framework, no ORM: plain
modules, argparse entry points, JSON/CSV state files committed to the repo.

It is a **calibration instrument, not a tipping service**. The whole design
goal is that a bug can never quietly stake money or invent a number.

## Commands

Dependencies: `pip install -r requirements.txt` (numpy, scipy, requests).

```bash
# The 07:00 run, end to end: grade -> fixtures -> odds -> engine -> verify -> board -> log -> notify
python run_daily.py                      # delivers to Telegram
python run_daily.py --no-send            # writes output/boards/ only
python run_daily.py --leagues Eredivisie "Scottish Premiership" --min-mes 0.02

# Scan without the daily-run wrapper (no grading, no logging, no delivery)
python orchestrator.py --all --season 2526
python orchestrator.py --league "Scottish Premiership" --season 2526

# Two-way Telegram channel (hourly in CI; run locally for instant replies)
python output/telegram_commands.py

# Is each whitelisted league actually able to produce a bet? (history/fixtures/odds/names)
python league_audit.py

# Historical CLV backtest and calibration
python backtest/clv_backtest.py --leagues Eredivisie --test-season 2425
python backtest/clv_backtest.py --selector random_placebo   # control arm
python backtest/calibration_check.py

# Regenerate EUROPEAN_COMPETITIONS.md from the live source directories
python generate_catalogue_doc.py
```

### Tests

Plain assert-based scripts, **not pytest** — each is run directly and prints a
`✅ ALL … PASSED` banner, exiting non-zero on failure.

```bash
for f in tests/*.py; do python "$f" || break; done
```

Two things to know before reading a failure:

- `tests/stress_test.py` **Stage 6 always fails off the Architect's Windows
  box.** It asserts `logs/launcher.log` exists, which only the Task Scheduler
  launcher (`run_daily.bat`) creates. 28 passed / 1 failed on Linux is green.
- `tests/stress_test.py` Stage 4 runs the **real pipeline against live data**
  and therefore mutates `clv/clv_log.json` and `output/boards/`. Revert those
  (`git checkout -- clv/clv_log.json output/boards/`) unless the state change
  is the point of your change.

## Architecture

Data flows one way; every stage degrades to `NO DATA — PENDING` rather than
guessing.

```
data/          fetch    football_data_source (history + closing odds, T1)
                        thesportsdb_fixtures / fixtures_source (upcoming)
                        api_football_results (history where FD has no coverage)
pipeline/odds  price    The Odds API entry price (quota-guarded)
engine/        model    dixon_coles  — bivariate Poisson, the primary model
                        elo          — independent second opinion, never blended
                        cross_league — pooled fit that makes UCL/UEL fittable
                        softness     — which leagues are deploy-eligible
                        markets      — canonical market keys + the ID405 gate
                        mes          — breakeven trigger price
verification/  check    id403 — multi-factor agreement -> VERIFIED / SINGLE-SOURCE
                                / CONFLICT / NO-DATA / DERIVED
output/        render   produce_bet (frozen board format) -> notify (Telegram)
clv/           log      clv_logger — the only instrument that proves edge
```

`orchestrator.py` owns the per-league scan (`scan_one_league`,
`run_all_leagues`). `run_daily.py` wraps it with yesterday's grading, paper-leg
logging and delivery. Prefer editing the orchestrator for scan logic and
`run_daily.py` for anything about the daily cycle.

### Committed state

`clv/clv_log.json`, `output/boards/`, `memory/corrections.csv` and
`memory/telegram_offset.json` are **live state committed back by CI**
(`daily board …`, `telegram commands …` commits). They are the Phase 3
evidence; do not rewrite or prune them to make a diff tidy.

## The rules that constrain changes

This codebase encodes a written blueprint. The shorthand appears everywhere in
comments; the ratification history is in `RATIFICATIONS.md` (append-only, per
HR33 — add an entry *when* you make a ratified change, never afterwards).

| Code | What it means in practice |
|---|---|
| **HR51 / Phase 2** | Paper only, zero capital. `config.assert_paper_only()` raises `CapitalGateError` on any stake below `PHASE = 3`. Phase 3 needs ≥30 logged legs, positive mean CLV, and the Architect's sign-off. |
| **HR35** | A gap is *reported*, never filled. Missing data renders `NO DATA — PENDING`; `CONFLICT` and `NO-DATA` are never resolved by picking a side. |
| **HR30 / HR46** | Every leg carries a numerical MES (breakeven trigger price) and a logged entry + closing price. |
| **HR53** | Full club names, markets spelled out in words — no truncation on the board. |
| **ID401 / ID402** | "Wide eyes, narrow hands": scan all 15 whitelisted leagues, but THE CALL only ever draws from softness tier A/B and is capped at `DEPLOY_POOL_CAP = 6` across all leagues combined. |
| **ID403 / ID404** | Verification is multi-factor agreement across *independent domains* — two pages of one site are one source. |
| **ID405** | Blocked markets are gated on canonical keys from `engine/markets.py`, never on display text. Compare keys; render with `display()`. |

Three bright lines are the Architect's alone and are never changed in code
without an explicit instruction: **enabling capital, moving the phase, and
removing the honest-edge caveat.** `output/telegram_commands.py` refuses all
three by design — a Telegram message is data, not authority.

## Conventions

- **Comments explain *why*, at length.** Most modules open with a docstring
  covering the bug or failure that motivated them. Match that density; a
  change that removes a guardrail should say why the guardrail is no longer
  needed.
- Entry points do `sys.path.insert(0, ...)` on the repo root and import
  `config` first — importing it loads `.env` for every entry point.
- Network access lives only in `data/`, `pipeline/odds.py` and `output/`.
  Everything downstream of a `MatchResult` list is pure and testable offline.
- Secrets come from `.env` (gitignored) locally and repo secrets in Actions;
  an existing environment variable always wins over `.env`.
- `*.bat`, `*.cmd`, `*.ps1` are CRLF per `.gitattributes` — the launcher runs
  on Windows Task Scheduler. `run_daily.bat` is deliberately minimal: logic
  belongs in Python where it is testable, and the alert path uses PowerShell
  so it cannot share a failure mode with a broken Python install.

## CI

- `.github/workflows/daily.yml` — 06:00 UTC (07:00 Africa/Lagos), runs
  `run_daily.py`, commits the CLV log and board back, and alerts Telegram on
  failure. A silent failure is treated as worse than no board.
- `.github/workflows/commands.yml` — hourly Telegram poll, commits logged legs
  and notes back. Hourly, not 15-minutely, to stay inside the free Actions
  allowance.

Both commit with `[skip ci]`. Do not remove that marker.
