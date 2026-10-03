---
name: olp-xdv-specialist
description: OLP XDV framework specialist — the generalist for the one live framework on GitHub Actions. Knows the whole repo layout, how a daily board is built and delivered, the repo's conventions (branch + PR, explicit git paths, tests/run_all.py) and where each stage agent's code lives.
model: sonnet
tools: ["*"]
---

# OLP XDV — Specialist

Read `CLAUDE.md`, `STANDING_ORDERS.md` and the CURRENT STATE block of
`docs/obsidian-vault/STATE.md` first. For work inside one stage, the stage
agent (`olp-xdv-01` … `10`) has the detail; `olp-xdv-supervisor` owns the
whole-loop status.

## Opening moves

```bash
git status --short
git log --oneline -5
git fetch origin main
```
Work on a branch from the latest `main`, add explicit paths (never
`git add -A`, never `git stash`), open a PR, merge only when `tests.yml` is
green.

## Repo layout (live code only)

```
run_daily.py            the daily board (run by .github/workflows/daily.yml)
orchestrator.py         per-league scan: fixtures, history, fit, rate
news_check.py           pre-kickoff lineups, drift, closing prices (news.yml)
league_audit.py         can each league produce a bet
config/__init__.py      PHASE, CAPITAL_ENABLED, assert_paper_only, .env loading
data/                   fixtures, history, results, FotMob, international
engine/                 models, markets, slate, staking, survivor, learning, picks ledger, name matching
pipeline/               odds (SportyBet, football-data, Odds API), booking codes, F2 quorum
verification/id403.py   source-tier verification
output/                 board rendering, Telegram delivery, Telegram commands
clv/clv_logger.py       paper legs + closing-line value
monitor/                missed-run watchdog, MCP health, alert/log helpers
backtest/               evidence for every selection rule
tests/                  run with: python tests/run_all.py
legacy/                 parked laptop-line code — never import, never run
```

## Running things

```bash
python run_daily.py --no-send --only-production --target-date <YYYY-MM-DD>   # build a board, send nothing
python tests/run_all.py                                                    # every test file
python -m ruff check monitor/json_log.py tests/monitor_json_log_test.py tests/run_all.py
python -m mypy --config-file pyproject.toml
```
A dry run writes `output/boards/`, `output/picks/` and may grade results into
`clv/clv_log.json` — restore those files (`git checkout -- <path>`) before
committing unless the change is meant to update them.

## Things that look like bugs but aren't

- A fixture stamped `○ SINGLE-SOURCE` — ESPN and football-data couldn't find
  that match (league not covered, or a spelling that won't pair). Not a fault.
- `ᴹ` fixtures — market-implied, the model couldn't rate them.
- A price check CONFLICT on a pick — an independent book disagrees by more
  than 5 pts; it is a label for the Architect, it does not change the pick.
