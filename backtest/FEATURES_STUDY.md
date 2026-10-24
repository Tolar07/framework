# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

483 fixtures, 2026-10-04 to 2026-10-23.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 483 |
| with xG form (both teams, 2+ prior matches) | 49 |
| with team news | 378 |
| with confirmed lineups | 41 |
| with SportyBet close | 415 |
| with Matchbook (sharp) close | 193 |
| with Betfair Exchange close | 255 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 49 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| home win | team-news edge | 378 | 269 | 0.2206 | +0.00062 | 0.00292 | NO CLEAR EFFECT |
| home win | soft close gap | 415 | 288 | 0.2222 | +0.00191 | 0.00338 | NO CLEAR EFFECT |
| home win | sharp close gap | 193 | 104 | 0.2176 | -0.01032 | 0.00668 | NO CLEAR EFFECT |
| home win | Betfair close gap | 255 | 166 | 0.2221 | +0.00470 | 0.00566 | NO CLEAR EFFECT |
| over 2.5 | xG total | 49 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| over 2.5 | soft close gap | 415 | 288 | 0.2450 | +0.00188 | 0.00157 | NO CLEAR EFFECT |
| over 2.5 | sharp close gap | 193 | 104 | 0.2435 | +0.00098 | 0.00791 | NO CLEAR EFFECT |
| over 2.5 | Betfair close gap | 255 | 166 | 0.2441 | +0.00348 | 0.00259 | NO CLEAR EFFECT |
| BTTS yes | xG total | 49 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| BTTS yes | soft close gap | 415 | 288 | 0.2491 | +0.00055 | 0.00261 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 193 | 104 | 0.2385 | -0.01105 | 0.00856 | NO CLEAR EFFECT |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
