# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

432 fixtures, 2026-10-04 to 2026-10-19.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 432 |
| with xG form (both teams, 2+ prior matches) | 11 |
| with team news | 331 |
| with confirmed lineups | 0 |
| with SportyBet close | 366 |
| with Matchbook (sharp) close | 147 |
| with Betfair Exchange close | 138 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 11 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| home win | team-news edge | 331 | 222 | 0.2174 | +0.00107 | 0.00337 | NO CLEAR EFFECT |
| home win | soft close gap | 366 | 239 | 0.2207 | +0.00125 | 0.00370 | NO CLEAR EFFECT |
| home win | sharp close gap | 147 | 58 | 0.2105 | -0.02042 | 0.01023 | NOT ENOUGH DATA |
| home win | Betfair close gap | 138 | 49 | 0.2240 | +0.01666 | 0.00766 | NOT ENOUGH DATA |
| over 2.5 | xG total | 11 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| over 2.5 | soft close gap | 366 | 239 | 0.2469 | +0.00234 | 0.00151 | NO CLEAR EFFECT |
| over 2.5 | sharp close gap | 147 | 58 | 0.2497 | +0.00515 | 0.01172 | NOT ENOUGH DATA |
| over 2.5 | Betfair close gap | 138 | 49 | 0.2599 | +0.00088 | 0.00333 | NOT ENOUGH DATA |
| BTTS yes | xG total | 11 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| BTTS yes | soft close gap | 366 | 239 | 0.2527 | +0.00181 | 0.00278 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 147 | 58 | 0.2441 | -0.00913 | 0.01292 | NOT ENOUGH DATA |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
