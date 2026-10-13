# NBA LADDER STUDY — the spread SportyBet's ladders assume

Written by `backtest/nba_ladder_study.py` from every saved SportyBet NBA ladder (`output/nba_ladders/`). Implied spread = the sd of the Normal curve that best fits the ladder's margin-free prices (`engine/nba_ladder.fit`).

OPEN LINES ONLY: 40 older snapshots were dropped — they mixed in closed lines (SportyBet status 2: listed with stale prices, not bettable), which faked a too-wide ladder.

388 looks at 32 games, 2026-10-07 to 2026-10-13. Regular season and preseason are measured apart (preseason rests starters).

## Regular

No ladder saved yet — NO DATA — PENDING.

## Preseason — 388 looks at 32 games

| Market | ladders | implied sd (median) | measured sd | ladder is | value per side in band: median · best |
|---|---|---|---|---|---|
| Full-game total | 387 | 18.71 | 18.0 | about right | -6.0% · +1.8% |
| Home points | 388 | 11.91 | 11.3 | WIDER by 0.6 | -7.0% · +4.6% |
| Away points | 388 | 11.80 | 11.3 | about right | -7.1% · +1.2% |
| Full-game handicap | 388 | 14.55 | 13.7 | WIDER by 0.9 | -6.3% · +5.7% |

Value uses the board's fair chance (sharp line + measured spread, margin removed); the board itself still needs +3% (winner) / +5% (lines) and a chance of 50%+ to pick.

