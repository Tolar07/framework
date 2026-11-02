# OLP XDV framework

The engine of OLP XDV. It runs on GitHub Actions: it builds the daily football and NBA boards and booking codes,
judges them (reasoning panel, fact sheet), tracks prices, grades every pick and every bot bet, and learns
from the results. The bots (Matchbook, SportyBet, Betfair, Trading) read what it publishes.

Since 30-10-2026 the picks, records and learning memory are published to the private `framework-data` repo
(`monitor/fdata.py`). This public repo keeps the code.

## Start here

1. `CLAUDE.md`: session startup and working rules.
2. `STANDING_ORDERS.md`: the Architect's standing rules (enforced by `tests/standing_orders_test.py`).
3. `MAP.md`: every workflow, secret, stored file and outside dependency.

## Layout

| Path | What it holds |
|---|---|
| `engine/` | Models (Dixon-Coles, Elo, calibration), reasoning, learning, inputs |
| `pipeline/`, `run_daily.py`, `run_nba.py`, `orchestrator.py` | The daily / NBA board builds |
| `monitor/` | Watchers: line-ups, news, prices, bot grader, data publishing |
| `backtest/`, `research/`, `verification/`, `clv/` | Studies, hypotheses, walk-forward checks, CLV |
| `config/` | League and market configuration |
| `tests/` | Test suite (`pytest`) |
| `docs/` | Framework docs and the Obsidian vault (`docs/obsidian-vault/`) |
| `legacy/` | Parked laptop-era code, never run |
| `.github/workflows/` | The schedules (daily, live, universe, reasoning, retrain, weekly, watchdog ...) |

## Test

```bash
pip install -r requirements.txt pytest
python -m pytest -q
```

## Project docs

Part of OLP XDV. The architecture, repo list, standards and dependency map are in the docs hub: [Tolar07/omniroute-test/docs](https://github.com/Tolar07/omniroute-test/blob/main/docs/README.md). Every Claude session reads and posts to the pinned [omniroute-test#54](https://github.com/Tolar07/omniroute-test/issues/54).
