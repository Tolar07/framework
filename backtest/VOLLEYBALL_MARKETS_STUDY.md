# Volleyball set-market shadow

Made 2026-11-07 04:11 UTC by `backtest/volleyball_markets_study.py` (framework#342). Record only.

Candidate: momentum score model (Elo K24, no home edge). **5 settings tried** (m = 0.0, 0.05, 0.1, 0.15, 0.2); chosen on 2016-2020 (best m = 0.15); reported on **2021-2025 only** (8830 matches).

| Market (held-out years) | Model Brier | Flat-rate Brier | Model better by |
|---|---|---|---|
| Over 3.5 sets | 0.2382 | 0.2516 | +0.0134 |
| Over 4.5 sets (five sets) | 0.1543 | 0.1569 | +0.0026 |
| Home -1.5 sets | 0.1877 | 0.2502 | +0.0625 |
| Away -1.5 sets | 0.1631 | 0.2203 | +0.0572 |

## Reading

- Model beats the flat rate on 4 of 4 markets (a shadow candidate for the set markets, to be confirmed on the shadow board).
- College data, not the pro leagues in scope. No free closing odds, so this is accuracy, not return.
- Record only: nothing here changes a stake, a bar or the live switch.
