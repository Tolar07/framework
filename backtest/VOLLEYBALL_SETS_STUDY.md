# Volleyball set-score shadow

Made 2026-11-07 03:10 UTC by `backtest/volleyball_sets_study.py` (framework#342, #380). Record only.

Candidate: per-set chance solved from the Elo match chance (K24, no home edge), sets independent. **1 setting tried.** Flat shares fitted on 2016-2020; reported on **2021-2025 only** (8830 matches).

| Rule | Log loss of the actual score (lower is better) |
|---|---|
| Elo -> best-of-5 score model | 1.5894 |
| Flat historical score shares | 1.7146 |

## Reading

- Score model vs flat shares: +0.1252 log loss (the Elo-driven score model beats the flat shares: a shadow candidate for correct-score / set markets).
- Straight-sets share: model 31.0% vs actual 48.7% (gap: sets are not independent; a momentum/set-correlation term is the next study).
- College data, not the pro leagues in scope. No free closing odds, so this is accuracy, not return.
- Record only: nothing here changes a stake, a bar or the live switch.
