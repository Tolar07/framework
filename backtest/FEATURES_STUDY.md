# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

459 fixtures, 2026-10-04 to 2026-10-20.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 459 |
| with xG form (both teams, 2+ prior matches) | 33 |
| with team news | 358 |
| with confirmed lineups | 22 |
| with SportyBet close | 393 |
| with Matchbook (sharp) close | 173 |
| with Betfair Exchange close | 239 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 33 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| home win | team-news edge | 358 | 249 | 0.2185 | +0.00111 | 0.00306 | NO CLEAR EFFECT |
| home win | soft close gap | 393 | 266 | 0.2215 | +0.00091 | 0.00349 | NO CLEAR EFFECT |
| home win | sharp close gap | 173 | 84 | 0.2160 | -0.01406 | 0.00765 | NOT ENOUGH DATA |
| home win | Betfair close gap | 239 | 150 | 0.2204 | +0.00651 | 0.00584 | NO CLEAR EFFECT |
| over 2.5 | xG total | 33 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| over 2.5 | soft close gap | 393 | 266 | 0.2437 | +0.00187 | 0.00159 | NO CLEAR EFFECT |
| over 2.5 | sharp close gap | 173 | 84 | 0.2385 | +0.00070 | 0.00937 | NOT ENOUGH DATA |
| over 2.5 | Betfair close gap | 239 | 150 | 0.2462 | +0.00347 | 0.00247 | NO CLEAR EFFECT |
| BTTS yes | xG total | 33 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| BTTS yes | soft close gap | 393 | 266 | 0.2499 | -0.00008 | 0.00272 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 173 | 84 | 0.2383 | -0.01508 | 0.01013 | NOT ENOUGH DATA |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
