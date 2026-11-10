# Tennis book-gap study (shadow, record only)

Made 2026-11-10 22:25 UTC by `backtest/tennis_book_gap_study.py` (framework#345). Pinnacle's de-vigged close is a fixed offset; signals are the average-vs-Pinnacle gap and the price times a WTA flag; coefficients refit each year on earlier years only (ridge 50). Tries counted: **1** model (2 signals, no search).

| Held-out years | Matches | Model log loss | Pinnacle close log loss | Gain per match | Std error |
|---|---|---|---|---|---|
| 2022-2025 | 19441 | 0.58634 | 0.58634 | -0.00000 | 0.00022 |

| Fit for year | book gap (avg - Pinnacle) | WTA x price |
|---|---|---|
| 2022 | -0.0522 | +0.1477 |
| 2023 | -0.0896 | +0.1199 |
| 2024 | -0.0887 | +0.1081 |
| 2025 | -0.0947 | +0.1015 |

## Reading

- Gain -0.00000 log loss per match (-0.0 standard errors): not distinguishable from zero; Pinnacle already holds what the other books know. Keep pricing off the exchange.
- Book-gap coefficient above 0: the other books were right to lean away from Pinnacle; WTA coefficient above 0: favourites won more than the price said on that tour.
- Record only: nothing here changes a stake, a bar, a threshold or the live switch.
