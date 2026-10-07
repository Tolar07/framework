# NBA LADDER STUDY — the spread SportyBet's ladders assume

Written by `backtest/nba_ladder_study.py` from every saved SportyBet NBA ladder (`output/nba_ladders/`). Implied spread = the sd of the Normal curve that best fits the ladder's margin-free prices (`engine/nba_ladder.fit`).

5 looks at 5 games, 2026-10-07 to 2026-10-07. Regular season and preseason are measured apart (preseason rests starters).

## Regular

No ladder saved yet — NO DATA — PENDING.

## Preseason — 5 looks at 5 games

| Market | ladders | implied sd (median) | measured sd | ladder is | value per side in band: median · best |
|---|---|---|---|---|---|
| Full-game total | 5 | 20.58 | 18.0 | WIDER by 2.6 | -5.4% · +15.7% |
| Home points | 5 | 12.45 | 11.3 | WIDER by 1.1 | -6.9% · +1.8% |
| Away points | 5 | 16.55 | 11.3 | WIDER by 5.2 | -4.9% · +30.1% |
| Full-game handicap | 5 | 16.77 | 13.7 | WIDER by 3.1 | -4.3% · +17.7% |

Value uses the board's fair chance (sharp line + measured spread, margin removed); the board itself still needs +3% (winner) / +5% (lines) and a chance of 50%+ to pick.

