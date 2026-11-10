# Tennis workload study (shadow, record only)

Made 2026-11-10 03:40 UTC by `backtest/tennis_workload_study.py` (framework#345). Pinnacle's de-vigged close is a fixed offset; signals are rest-day gap, matches in the last 14 days and a Best-of-5 interaction, from the results list only; coefficients refit each year on earlier years only (ridge 50). Tries counted: **1** model (3 signals, no search).

| Held-out years | Matches | Model log loss | Pinnacle close log loss | Gain per match | Std error |
|---|---|---|---|---|---|
| 2022-2025 | 18975 | 0.58977 | 0.58967 | -0.00010 | 0.00027 |

| Fit for year | rest gap (log days, a vs b) | matches in last 14 days (a minus b) | Bo5 x load gap |
|---|---|---|---|
| 2022 | -0.0659 | +0.0328 | -0.0584 |
| 2023 | -0.0545 | +0.0270 | -0.0475 |
| 2024 | -0.0396 | +0.0237 | -0.0338 |
| 2025 | -0.0309 | +0.0282 | -0.0415 |

## Reading

- Gain -0.00010 log loss per match (-0.4 standard errors): not distinguishable from zero; the price already holds workload. Keep pricing off the exchange.
- Coefficients near 0 mean the close already reflects rest and recent load.
- Record only: nothing here changes a stake, a bar, a threshold or the live switch.
