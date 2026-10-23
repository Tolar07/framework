# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

464 fixtures, 2026-10-04 to 2026-10-21.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 464 |
| with xG form (both teams, 2+ prior matches) | 35 |
| with team news | 361 |
| with confirmed lineups | 24 |
| with SportyBet close | 398 |
| with Matchbook (sharp) close | 178 |
| with Betfair Exchange close | 255 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 35 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| home win | team-news edge | 361 | 252 | 0.2200 | +0.00085 | 0.00303 | NO CLEAR EFFECT |
| home win | soft close gap | 398 | 271 | 0.2227 | +0.00068 | 0.00350 | NO CLEAR EFFECT |
| home win | sharp close gap | 178 | 89 | 0.2200 | -0.01392 | 0.00753 | NOT ENOUGH DATA |
| home win | Betfair close gap | 255 | 166 | 0.2221 | +0.00470 | 0.00566 | NO CLEAR EFFECT |
| over 2.5 | xG total | 35 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| over 2.5 | soft close gap | 398 | 271 | 0.2428 | +0.00158 | 0.00157 | NO CLEAR EFFECT |
| over 2.5 | sharp close gap | 178 | 89 | 0.2361 | -0.00079 | 0.00882 | NOT ENOUGH DATA |
| over 2.5 | Betfair close gap | 255 | 166 | 0.2441 | +0.00348 | 0.00259 | NO CLEAR EFFECT |
| BTTS yes | xG total | 35 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| BTTS yes | soft close gap | 398 | 271 | 0.2497 | +0.00032 | 0.00270 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 178 | 89 | 0.2385 | -0.01302 | 0.00973 | NOT ENOUGH DATA |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
