# NBA LADDER STUDY — the spread SportyBet's ladders assume

Written by `backtest/nba_ladder_study.py` from every saved SportyBet NBA ladder (`output/nba_ladders/`). Implied spread = the sd of the Normal curve that best fits the ladder's margin-free prices (`engine/nba_ladder.fit`).

OPEN LINES ONLY: 40 older snapshots were dropped — they mixed in closed lines (SportyBet status 2: listed with stale prices, not bettable), which faked a too-wide ladder.

1353 looks at 81 games, 2026-10-07 to 2026-10-23. Regular season and preseason are measured apart (preseason rests starters).

## Regular — 436 looks at 28 games

| Market | ladders | implied sd (median) | measured sd | ladder is | value per side in band: median · best |
|---|---|---|---|---|---|
| Full-game total | 436 | 18.38 | 18.0 | about right | -4.2% · +2.3% |
| Home points | 425 | 11.69 | 11.3 | about right | -4.7% · +6.2% |
| Away points | 425 | 11.63 | 11.3 | about right | -4.7% · +3.8% |
| Regulation total | 0 | — | 17.2 | PENDING | -4.0% · +3.0% |
| Full-game handicap | 436 | 14.95 | 13.7 | WIDER by 1.2 | -3.0% · +8.5% |
| 1st-half handicap | 425 | 11.68 | 11.0 | WIDER by 0.7 | -4.0% · +3.9% |
| 1st-quarter handicap | 425 | 8.81 | 8.3 | WIDER by 0.5 | -5.3% · -0.6% |
| 2nd-quarter handicap | 425 | 8.89 | 8.2 | WIDER by 0.7 | -5.2% · +2.8% |
| 3rd-quarter handicap | 425 | 8.81 | 8.5 | about right | -5.0% · +1.0% |
| 4th-quarter handicap | 425 | 8.28 | — | PENDING | — |

## Preseason — 917 looks at 53 games

| Market | ladders | implied sd (median) | measured sd | ladder is | value per side in band: median · best |
|---|---|---|---|---|---|
| Full-game total | 916 | 18.72 | 18.0 | about right | -6.0% · +1.8% |
| Home points | 917 | 12.06 | 11.3 | WIDER by 0.8 | -7.0% · +4.6% |
| Away points | 917 | 11.81 | 11.3 | about right | -7.1% · +1.2% |
| Full-game handicap | 917 | 14.98 | 13.7 | WIDER by 1.3 | -6.3% · +6.0% |

Value uses the board's fair chance (sharp line + measured spread, margin removed); the board itself still needs +3% (winner) / +5% (lines) and a chance of 50%+ to pick.

