# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

759 fixtures, 2026-10-04 to 2026-10-30.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 759 |
| with xG form (both teams, 2+ prior matches) | 234 |
| with team news | 634 |
| with confirmed lineups | 292 |
| with SportyBet close | 677 |
| with Matchbook (sharp) close | 452 |
| with Betfair Exchange close | 415 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 234 | 181 | 0.2158 | -0.00064 | 0.00114 | NO CLEAR EFFECT |
| home win | team-news edge | 634 | 525 | 0.2212 | -0.00138 | 0.00186 | NO CLEAR EFFECT |
| home win | soft close gap | 677 | 550 | 0.2232 | +0.00314 | 0.00252 | NO CLEAR EFFECT |
| home win | sharp close gap | 452 | 362 | 0.2213 | +0.00119 | 0.00355 | NO CLEAR EFFECT |
| home win | Betfair close gap | 415 | 326 | 0.2234 | +0.00670 | 0.00393 | NO CLEAR EFFECT |
| over 2.5 | xG total | 234 | 181 | 0.2336 | +0.00060 | 0.00085 | NO CLEAR EFFECT |
| over 2.5 | soft close gap | 677 | 550 | 0.2406 | +0.00310 | 0.00164 | NO CLEAR EFFECT |
| over 2.5 | sharp close gap | 452 | 362 | 0.2378 | +0.00452 | 0.00388 | NO CLEAR EFFECT |
| over 2.5 | Betfair close gap | 415 | 326 | 0.2388 | +0.00504 | 0.00249 | ADDS INFORMATION |
| BTTS yes | xG total | 234 | 181 | 0.2319 | -0.00048 | 0.00060 | NO CLEAR EFFECT |
| BTTS yes | soft close gap | 677 | 550 | 0.2419 | +0.00046 | 0.00190 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 449 | 359 | 0.2340 | -0.00375 | 0.00325 | NO CLEAR EFFECT |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
