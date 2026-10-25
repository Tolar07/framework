# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

596 fixtures, 2026-10-04 to 2026-10-24.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 596 |
| with xG form (both teams, 2+ prior matches) | 124 |
| with team news | 482 |
| with confirmed lineups | 144 |
| with SportyBet close | 523 |
| with Matchbook (sharp) close | 298 |
| with Betfair Exchange close | 255 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 124 | 72 | 0.2351 | -0.00002 | 0.00216 | NOT ENOUGH DATA |
| home win | team-news edge | 482 | 373 | 0.2255 | -0.00206 | 0.00250 | NO CLEAR EFFECT |
| home win | soft close gap | 523 | 396 | 0.2260 | +0.00299 | 0.00289 | NO CLEAR EFFECT |
| home win | sharp close gap | 298 | 209 | 0.2267 | -0.00147 | 0.00449 | NO CLEAR EFFECT |
| home win | Betfair close gap | 255 | 166 | 0.2221 | +0.00470 | 0.00566 | NO CLEAR EFFECT |
| over 2.5 | xG total | 124 | 72 | 0.2406 | -0.00038 | 0.00162 | NOT ENOUGH DATA |
| over 2.5 | soft close gap | 523 | 396 | 0.2449 | +0.00311 | 0.00159 | NO CLEAR EFFECT |
| over 2.5 | sharp close gap | 298 | 209 | 0.2435 | +0.00465 | 0.00514 | NO CLEAR EFFECT |
| over 2.5 | Betfair close gap | 255 | 166 | 0.2441 | +0.00348 | 0.00259 | NO CLEAR EFFECT |
| BTTS yes | xG total | 124 | 72 | 0.2391 | -0.00057 | 0.00122 | NOT ENOUGH DATA |
| BTTS yes | soft close gap | 523 | 396 | 0.2474 | +0.00172 | 0.00225 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 298 | 209 | 0.2401 | -0.00337 | 0.00496 | NO CLEAR EFFECT |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
