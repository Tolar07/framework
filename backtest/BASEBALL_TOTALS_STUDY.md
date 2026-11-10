# Baseball (MLB) total-runs walk-forward backtest

Made 2026-11-10 04:14 UTC by `backtest/baseball_totals_backtest.py` (framework#346). 15730 MLB games 2019-2025 with a closing total line and Over/Under prices (cached ESPN scoreboard + odds record, median pre-game bookmaker). Tries counted: **30** (decay x shrink x park x market weight, then the edge bars). Chosen on 2019-2022, reported on **2023-2025 only** (7394 games).

Not loaded: 2019: 19 of 2470 games without a closing total (skipped); 2020: 9 of 953 games without a closing total (skipped); 2021: 15 of 2475 games without a closing total (skipped); 2022: 6 of 2472 games without a closing total (skipped); 2023: 1 of 2478 games without a closing total (skipped); 2024: 24 of 2476 games without a closing total (skipped); 2025: 2 of 2482 games without a closing total (skipped)

| Rule (held-out seasons) | Games | RMSE of the total (runs) |
|---|---|---|
| The closing total line | 7394 | 4.465 |
| Model alone (decay 0.97, shrink 30, park 1) | 7394 | 4.462 |
| Best blend on tuning seasons (same model, market weight 75%) | 7394 | 4.440 |

## Flat-stake test (Over/Under vs the closing line, pushes dropped)

| Setting | Edge bar (runs) | Bets | ROI at the bookmaker close | ROI at an even price less 2% commission |
|---|---|---|---|---|
| Model alone | 0.5 | 4358 | -3.7% | +0.7% |
| Best blend | 0.5 | 209 | -10.2% | -4.3% |
| Model alone | 1.0 | 2134 | -4.1% | +0.8% |
| Best blend | 1.0 | 5 | +13.6% | +18.8% |

## Reading

- Model alone RMSE 4.462 vs the close 4.465: level with the closing total (a gap this small is noise, not an edge).
- Best blend RMSE 4.440 vs the close 4.465 (-0.025): a small gain beyond the line held-out, under 0.05 runs: noise until a shadow confirms it.
- 30 tries made; the held-out lines are the honest ones, any ROI above is one of them, not a result to bank.
- No starting-pitcher, weather or bullpen input here (the biggest total movers): PENDING; weather and wind are not in the free cache.
- Record only: nothing here changes a stake, a bar, a threshold or the live switch.
