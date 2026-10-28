# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

715 fixtures, 2026-10-04 to 2026-10-27.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 715 |
| with xG form (both teams, 2+ prior matches) | 195 |
| with team news | 591 |
| with confirmed lineups | 249 |
| with SportyBet close | 633 |
| with Matchbook (sharp) close | 408 |
| with Betfair Exchange close | 385 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 195 | 142 | 0.2197 | -0.00078 | 0.00144 | NO CLEAR EFFECT |
| home win | team-news edge | 591 | 482 | 0.2224 | -0.00138 | 0.00199 | NO CLEAR EFFECT |
| home win | soft close gap | 633 | 506 | 0.2242 | +0.00372 | 0.00257 | NO CLEAR EFFECT |
| home win | sharp close gap | 408 | 318 | 0.2226 | +0.00172 | 0.00367 | NO CLEAR EFFECT |
| home win | Betfair close gap | 385 | 296 | 0.2247 | +0.00621 | 0.00412 | NO CLEAR EFFECT |
| over 2.5 | xG total | 195 | 142 | 0.2380 | -0.00023 | 0.00088 | NO CLEAR EFFECT |
| over 2.5 | soft close gap | 633 | 506 | 0.2422 | +0.00400 | 0.00162 | ADDS INFORMATION |
| over 2.5 | sharp close gap | 408 | 318 | 0.2401 | +0.00692 | 0.00406 | NO CLEAR EFFECT |
| over 2.5 | Betfair close gap | 385 | 296 | 0.2437 | +0.00630 | 0.00256 | ADDS INFORMATION |
| BTTS yes | xG total | 195 | 142 | 0.2362 | -0.00106 | 0.00059 | NO CLEAR EFFECT |
| BTTS yes | soft close gap | 633 | 506 | 0.2431 | +0.00078 | 0.00195 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 408 | 318 | 0.2360 | -0.00335 | 0.00348 | NO CLEAR EFFECT |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
