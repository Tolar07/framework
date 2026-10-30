# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

741 fixtures, 2026-10-04 to 2026-10-29.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 741 |
| with xG form (both teams, 2+ prior matches) | 217 |
| with team news | 616 |
| with confirmed lineups | 274 |
| with SportyBet close | 658 |
| with Matchbook (sharp) close | 433 |
| with Betfair Exchange close | 415 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 217 | 164 | 0.2122 | -0.00072 | 0.00125 | NO CLEAR EFFECT |
| home win | team-news edge | 616 | 507 | 0.2203 | -0.00153 | 0.00191 | NO CLEAR EFFECT |
| home win | soft close gap | 658 | 531 | 0.2220 | +0.00319 | 0.00250 | NO CLEAR EFFECT |
| home win | sharp close gap | 433 | 343 | 0.2194 | +0.00109 | 0.00350 | NO CLEAR EFFECT |
| home win | Betfair close gap | 415 | 326 | 0.2234 | +0.00670 | 0.00393 | NO CLEAR EFFECT |
| over 2.5 | xG total | 217 | 164 | 0.2383 | +0.00020 | 0.00085 | NO CLEAR EFFECT |
| over 2.5 | soft close gap | 658 | 531 | 0.2423 | +0.00367 | 0.00164 | ADDS INFORMATION |
| over 2.5 | sharp close gap | 433 | 343 | 0.2403 | +0.00594 | 0.00395 | NO CLEAR EFFECT |
| over 2.5 | Betfair close gap | 415 | 326 | 0.2388 | +0.00504 | 0.00249 | ADDS INFORMATION |
| BTTS yes | xG total | 217 | 164 | 0.2351 | -0.00065 | 0.00058 | NO CLEAR EFFECT |
| BTTS yes | soft close gap | 658 | 531 | 0.2431 | +0.00080 | 0.00190 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 430 | 340 | 0.2355 | -0.00334 | 0.00332 | NO CLEAR EFFECT |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
