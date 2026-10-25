# NBA LADDER STUDY — the spread SportyBet's ladders assume

Written by `backtest/nba_ladder_study.py` from every saved SportyBet NBA ladder (`output/nba_ladders/`). Implied spread = the sd of the Normal curve that best fits the ladder's margin-free prices (`engine/nba_ladder.fit`).

OPEN LINES ONLY: 40 older snapshots were dropped — they mixed in closed lines (SportyBet status 2: listed with stale prices, not bettable), which faked a too-wide ladder.

1733 looks at 96 games, 2026-10-07 to 2026-10-25. Regular season and preseason are measured apart (preseason rests starters).

## Regular — 816 looks at 43 games

| Market | ladders | implied sd (median) | measured sd | ladder is | value per side in band: median · best |
|---|---|---|---|---|---|
| Full-game total | 816 | 18.37 | 18.0 | about right | -4.0% · +2.3% |
| Home points | 805 | 11.68 | 11.3 | about right | -4.7% · +6.2% |
| Away points | 805 | 11.63 | 11.3 | about right | -4.8% · +3.8% |
| Regulation total | 0 | — | 17.2 | PENDING | -4.0% · +3.0% |
| Full-game handicap | 816 | 14.83 | 13.7 | WIDER by 1.1 | -3.4% · +8.5% |
| 1st-half handicap | 805 | 11.74 | 11.0 | WIDER by 0.7 | -4.0% · +5.2% |
| 1st-quarter handicap | 803 | 8.82 | 8.3 | WIDER by 0.5 | -5.3% · +0.9% |
| 2nd-quarter handicap | 803 | 8.95 | 8.2 | WIDER by 0.8 | -4.9% · +5.2% |
| 3rd-quarter handicap | 803 | 8.81 | 8.5 | about right | -4.9% · +1.0% |
| 4th-quarter handicap | 803 | 8.32 | — | PENDING | — |

## Preseason — 917 looks at 53 games

| Market | ladders | implied sd (median) | measured sd | ladder is | value per side in band: median · best |
|---|---|---|---|---|---|
| Full-game total | 916 | 18.72 | 18.0 | about right | -6.0% · +1.8% |
| Home points | 917 | 12.06 | 11.3 | WIDER by 0.8 | -7.0% · +4.6% |
| Away points | 917 | 11.81 | 11.3 | about right | -7.1% · +1.2% |
| Full-game handicap | 917 | 14.98 | 13.7 | WIDER by 1.3 | -6.3% · +6.0% |

Value uses the board's fair chance (sharp line + measured spread, margin removed); the board itself still needs +3% (winner) / +5% (lines) and a chance of 50%+ to pick.

