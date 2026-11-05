# NCAA STUDY — constants for an NCAA board

Written by `backtest/ncaa_study.py` (ESPN free scoreboard + odds feed, men's Division I, 2025-11-03 to 2026-03-08, sampled dates). 1752 finished games read, 1567 with a pre-tip sharp line (DraftKings, ESPN BET).

| Quantity | Mean miss (bias) | SD | inside ±1 SD (Normal ≈ 68%) | n | NBA board value |
|---|---|---|---|---|---|
| final total − sharp total | +0.56 | 17.22 | 70% | 1567 | SD 18.0 |
| home margin + sharp spread | -0.41 | 11.38 | 70% | 1567 | SD 13.7 |
| 1st-half total − share × sharp total (no OT games) | -0.00 | 10.41 | — | 1487 | share 0.502, SD 11.9 |

1st-half share of the sharp total: **0.4735**.

Use: an NCAA board would price SportyBet's total and handicap ladders as Normal(line + bias, SD) from these numbers, exactly as engine/nba_value.py does for the NBA, and qualify a pick only above its value bar. RECORDED ONLY until a forward test earns it a place (the Architect's call).
