# NBA LADDER STUDY — the spread SportyBet's ladders assume

Written by `backtest/nba_ladder_study.py` from every saved SportyBet NBA ladder (`output/nba_ladders/`). Implied spread = the sd of the Normal curve that best fits the ladder's margin-free prices (`engine/nba_ladder.fit`).

OPEN LINES ONLY: 40 older snapshots were dropped — they mixed in closed lines (SportyBet status 2: listed with stale prices, not bettable), which faked a too-wide ladder.

10 looks at 5 games, 2026-10-07 to 2026-10-07. Regular season and preseason are measured apart (preseason rests starters).

## Regular

No ladder saved yet — NO DATA — PENDING.

## Preseason — 10 looks at 5 games

| Market | ladders | implied sd (median) | measured sd | ladder is | value per side in band: median · best |
|---|---|---|---|---|---|
| Full-game total | 10 | 18.71 | 18.0 | about right | -6.0% · -2.1% |
| Home points | 10 | 12.05 | 11.3 | WIDER by 0.8 | -7.0% · -4.9% |
| Away points | 10 | 11.81 | 11.3 | about right | -7.1% · -1.6% |
| Full-game handicap | 10 | 15.82 | 13.7 | WIDER by 2.1 | -4.8% · -0.4% |

Value uses the board's fair chance (sharp line + measured spread, margin removed); the board itself still needs +3% (winner) / +5% (lines) and a chance of 50%+ to pick.

