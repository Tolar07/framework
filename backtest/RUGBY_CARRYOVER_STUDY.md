# Rugby off-season carry-over study (rating pulled back to the mean after a long break)

Made 2026-11-06 22:11 UTC by `backtest/rugby_carryover_study.py` (framework#344). 6064 games, final scores only (ESPN). Settings tried: **29**; chosen on 2014-2019, reported on **2020-2025 only**. A new season = a side's first game after more than 100 days.

| Rule (held-out years) | Games | Brier | Brier flat baseline (68.9%) | Winner hit rate |
|---|---|---|---|---|
| Live board: K24, no home edge | 2814 | 0.2206 | 0.2186 | 64.3% |
| Per-league home edge, full carry-over | 2814 | 0.1844 | 0.2186 | 72.2% |
| Per-league home edge + pull 10% to the mean each new season | 2814 | 0.1845 | 0.2186 | 71.8% |

## Reading

- Season pull 10% changed held-out Brier by -0.0001 vs full carry-over (no real help: not worth a shadow).
- 29 settings tried; the held-out line is the honest one.
- Record only: nothing here changes a stake, a bar or the live switch.
