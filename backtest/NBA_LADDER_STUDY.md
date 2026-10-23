# NBA LADDER STUDY — the spread SportyBet's ladders assume

Written by `backtest/nba_ladder_study.py` from every saved SportyBet NBA ladder (`output/nba_ladders/`). Implied spread = the sd of the Normal curve that best fits the ladder's margin-free prices (`engine/nba_ladder.fit`).

OPEN LINES ONLY: 40 older snapshots were dropped — they mixed in closed lines (SportyBet status 2: listed with stale prices, not bettable), which faked a too-wide ladder.

1248 looks at 69 games, 2026-10-07 to 2026-10-23. Regular season and preseason are measured apart (preseason rests starters).

## Regular — 331 looks at 16 games

| Market | ladders | implied sd (median) | measured sd | ladder is | value per side in band: median · best |
|---|---|---|---|---|---|
| Full-game total | 331 | 18.37 | 18.0 | about right | -4.0% · +2.3% |
| Home points | 329 | 11.69 | 11.3 | about right | -4.7% · +3.4% |
| Away points | 329 | 11.54 | 11.3 | about right | -4.7% · +1.9% |
| Regulation total | 0 | — | 17.2 | PENDING | -4.3% · +2.5% |
| Full-game handicap | 331 | 14.96 | 13.7 | WIDER by 1.3 | -3.0% · +5.6% |
| 1st-half handicap | 329 | 11.69 | 11.0 | WIDER by 0.7 | -4.0% · +3.5% |
| 1st-quarter handicap | 329 | 8.82 | 8.3 | WIDER by 0.5 | -5.3% · -1.5% |
| 2nd-quarter handicap | 329 | 8.89 | 8.2 | WIDER by 0.7 | -4.9% · +2.5% |
| 3rd-quarter handicap | 329 | 8.81 | 8.5 | about right | -4.9% · +1.0% |
| 4th-quarter handicap | 329 | 8.32 | — | PENDING | — |

## Preseason — 917 looks at 53 games

| Market | ladders | implied sd (median) | measured sd | ladder is | value per side in band: median · best |
|---|---|---|---|---|---|
| Full-game total | 916 | 18.72 | 18.0 | about right | -6.0% · +1.8% |
| Home points | 917 | 12.06 | 11.3 | WIDER by 0.8 | -7.0% · +4.6% |
| Away points | 917 | 11.81 | 11.3 | about right | -7.1% · +1.2% |
| Full-game handicap | 917 | 14.98 | 13.7 | WIDER by 1.3 | -6.3% · +6.0% |

Value uses the board's fair chance (sharp line + measured spread, margin removed); the board itself still needs +3% (winner) / +5% (lines) and a chance of 50%+ to pick.

