# Lineage merge — 2026-10-03

Two copies of OLP XDV grew apart from `7fbfbd4` (2026-08-04, "Pre-season
stress test: 31/31 pass") and were merged back into one history on
branch `claude/unify-lineages`:

| Line | Tip | Commits since split | Ran where |
|---|---|---|---|
| cloud (`main`) | `ebed17b` (2026-10-02) | 110 | GitHub Actions `daily.yml` (board → Telegram) |
| laptop (`elo-persistence`) | `81ef177` (2026-09-19) | 452 | Windows Task Scheduler, `run_daily.bat` |
| `claude/fix-cache-contamination` (PR #1) | `6a035a3` | 23 beyond the laptop line | — |
| `claude/odds-f2-quorum` (PR #6) | `4c7e7fa` | 1 | — |

The omniroute-test workspace's copy (`93c9337`) is an ancestor of the laptop
line, and the workspace-root `olpxdv_framework/` skeleton is now
`legacy/olpxdv_framework/`. All other `claude/*` branches were already in
`main` (squash-merged PRs). `claude/sportybet-odds-prototype` (PR #8, closed
unmerged) and `claude/claude-rc-xj5xfe` were superseded and not merged.

## Policy: main wins

Every file `main` already had keeps main's exact content, so the cloud daily
board runs the same code it ran before the merge. Verified by running all 21
of main's test scripts on both trees (identical pass/fail; the two that fail,
`engine_regression_test` and `stress_test`, fail identically on main) and a
`run_daily.py --no-send --only-production --target-date 2026-10-03` dry run
on both trees: byte-identical board.

Laptop-only files are all added. Laptop code that depended on the laptop
version of a file listed below will not work until ported: the laptop
`run_daily.py`/`run_daily.bat` loop in particular expects flags
(`--agreement-band`, `--date`) and Stage B wiring that main's `run_daily.py`
does not have.

Nothing is lost: each laptop version is in history. To see one:
`git show 81ef177:<path>` (laptop tip) or `git show 6a035a3:<path>` (PR #1).

### Conflicting files — main's version kept (laptop changes since split)

- `.github/workflows/daily.yml` — 4 commits, 24 insertions(+), 6 deletions(-)
- `backtest/backtest_report.py` — 4 commits, 69 insertions(+), 13 deletions(-)
- `backtest/clv_backtest.py` — 7 commits, 158 insertions(+), 33 deletions(-)
- `config/__init__.py` — 1 commits, 122 insertions(+)
- `data/flashscore_results.py` — 2 commits, 317 insertions(+)
- `data/football_data_source.py` — 10 commits, 246 insertions(+), 35 deletions(-)
- `engine/dixon_coles.py` — 5 commits, 125 insertions(+), 12 deletions(-)
- `engine/markets.py` — 10 commits, 349 insertions(+), 24 deletions(-)
- `league_audit.py` — 4 commits, 99 insertions(+), 22 deletions(-)
- `orchestrator.py` — 31 commits, 36 insertions(+), 313 deletions(-)
- `output/boards/board_2026-08-04.txt` — 1 commits, 16 insertions(+), 13 deletions(-)
- `output/boards/board_2026-08-05.txt` — 2 commits, 69 insertions(+)
- `output/boards/board_2026-08-06.txt` — 1 commits, 68 insertions(+)
- `output/boards/board_2026-09-01.txt` — 1 commits, 55 insertions(+)
- `output/boards/board_2026-09-12.txt` — 1 commits, 37 insertions(+)
- `output/boards/board_2026-09-16.txt` — 1 commits, 81 insertions(+)
- `output/boards/board_2026-09-17.txt` — 2 commits, 343 insertions(+)
- `output/boards/board_2026-09-18.txt` — 1 commits, 474 insertions(+)
- `output/notify.py` — 9 commits, 217 insertions(+), 25 deletions(-)
- `output/produce_bet.py` — 54 commits, 1877 insertions(+), 153 deletions(-)
- `output/telegram_commands.py` — 21 commits, 768 insertions(+), 71 deletions(-)
- `pipeline/odds.py` — 18 commits, 389 insertions(+), 72 deletions(-)
- `run_daily.py` — 87 commits, 1124 insertions(+), 276 deletions(-)
- `tests/engine_regression_test.py` — 9 commits, 103 insertions(+), 24 deletions(-)
- `tests/multi_league_test.py` — 8 commits, 46 insertions(+), 24 deletions(-)
- `tests/stress_test.py` — 4 commits, 19 insertions(+), 12 deletions(-)

### Conflicts with PR #1 — unified line's version kept

- `booking/bridge.py`, `booking/rebuild_cache.py`, `booking/sportybet_fixtures.py`,
  `config/leagues.json`, `data/flashscore_results.py`, `data/multi_source_concrete.py`,
  `engine/acca.py`, `olp_xdv_pipeline.py`, `output/notify.py`, `output/produce_bet.py`,
  `output/telegram_commands.py`, `pipeline/production_stage_b.py`,
  `tests/cache_freshness_test.py` (laptop-tip version where main has no copy).
- `requirements.txt`: unified, plus `python-dotenv` from PR #1.

### Clean laptop edits to main's files — reverted to main

These merged without a textual conflict but changed live behaviour (e.g. the
`engine/mes.py` edit broke `slate_test`), so they were reverted to main:

- `clv/clv_logger.py` — 303 insertions(+), 1 deletion(-)
- `data/api_football_results.py` — 49 insertions(+), 22 deletions(-)
- `data/fixtures_source.py` — 174 insertions(+), 8 deletions(-)
- `data/thesportsdb_fixtures.py` — 906 insertions(+), 31 deletions(-)
- `engine/cross_league.py` — 193 insertions(+), 5 deletions(-)
- `engine/dixon_coles.py` — 15 insertions(+)
- `engine/elo.py` — 224 insertions(+), 27 deletions(-)
- `engine/mes.py` — 43 insertions(+), 18 deletions(-)
- `memory/corrections.csv` — 1 insertion(+)
- `pipeline/odds.py` — 5 insertions(+)
- `tests/clv_backtest_test.py` — 98 insertions(+)
- `verification/id403.py` — 12 insertions(+), 1 deletion(-)

`pipeline/odds.py`'s 5-line hook from PR #6 is among them: `pipeline/odds_verify.py`
and its passing test are in, but F2 quorum is not wired into the live odds path.

`data/__init__.py` (laptop) was removed: it eagerly imported laptop-only names
from `data/football_data_source.py`, which broke every `from data import …`
under main's version of that file. No code used its re-exports.

### Other merge fixes

- `config.py` → `config/__init__.py`: git followed the laptop line's move. The
  content is main's `config.py` (PHASE 3 and every gate unchanged) except
  `load_dotenv` now resolves `.env` at the repo root instead of `config/.env`.
- `.gitignore`: laptop rules (`*.jsonl`, `clv/clv_log*.json`, `.env.*`) would hide
  new files the cloud workflow commits; added re-includes for them.
- `.claude/settings.local.json` restored (the laptop line deleted it).
- `backtest.yml` and `fixture-extraction.yml` (laptop) are `workflow_dispatch`
  only: on push / at 04:00 they committed to main and ran a second pipeline with
  the Telegram token and `ARCHITECT_SIGNOFF`. `tests.yml` and `sync-health.yml`
  (read-only) run as written.
