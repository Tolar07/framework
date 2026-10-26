# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

667 fixtures, 2026-10-04 to 2026-10-25.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 667 |
| with xG form (both teams, 2+ prior matches) | 167 |
| with team news | 547 |
| with confirmed lineups | 209 |
| with SportyBet close | 592 |
| with Matchbook (sharp) close | 367 |
| with Betfair Exchange close | 255 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 167 | 115 | 0.2217 | -0.00024 | 0.00154 | NO CLEAR EFFECT |
| home win | team-news edge | 547 | 438 | 0.2240 | -0.00198 | 0.00218 | NO CLEAR EFFECT |
| home win | soft close gap | 592 | 465 | 0.2246 | +0.00378 | 0.00264 | NO CLEAR EFFECT |
| home win | sharp close gap | 367 | 278 | 0.2242 | +0.00138 | 0.00379 | NO CLEAR EFFECT |
| home win | Betfair close gap | 255 | 166 | 0.2221 | +0.00470 | 0.00566 | NO CLEAR EFFECT |
| over 2.5 | xG total | 167 | 115 | 0.2387 | +0.00015 | 0.00114 | NO CLEAR EFFECT |
| over 2.5 | soft close gap | 592 | 465 | 0.2437 | +0.00354 | 0.00168 | ADDS INFORMATION |
| over 2.5 | sharp close gap | 367 | 278 | 0.2419 | +0.00594 | 0.00455 | NO CLEAR EFFECT |
| over 2.5 | Betfair close gap | 255 | 166 | 0.2441 | +0.00348 | 0.00259 | NO CLEAR EFFECT |
| BTTS yes | xG total | 167 | 115 | 0.2391 | -0.00046 | 0.00078 | NO CLEAR EFFECT |
| BTTS yes | soft close gap | 592 | 465 | 0.2455 | +0.00145 | 0.00210 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 367 | 278 | 0.2388 | -0.00239 | 0.00406 | NO CLEAR EFFECT |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
