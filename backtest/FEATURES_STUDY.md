# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

689 fixtures, 2026-10-04 to 2026-10-26.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 689 |
| with xG form (both teams, 2+ prior matches) | 178 |
| with team news | 565 |
| with confirmed lineups | 225 |
| with SportyBet close | 607 |
| with Matchbook (sharp) close | 382 |
| with Betfair Exchange close | 385 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 178 | 125 | 0.2214 | -0.00075 | 0.00163 | NO CLEAR EFFECT |
| home win | team-news edge | 565 | 456 | 0.2239 | -0.00163 | 0.00210 | NO CLEAR EFFECT |
| home win | soft close gap | 607 | 480 | 0.2255 | +0.00394 | 0.00262 | NO CLEAR EFFECT |
| home win | sharp close gap | 382 | 292 | 0.2247 | +0.00186 | 0.00380 | NO CLEAR EFFECT |
| home win | Betfair close gap | 385 | 296 | 0.2247 | +0.00621 | 0.00412 | NO CLEAR EFFECT |
| over 2.5 | xG total | 178 | 125 | 0.2400 | -0.00033 | 0.00099 | NO CLEAR EFFECT |
| over 2.5 | soft close gap | 607 | 480 | 0.2440 | +0.00433 | 0.00165 | ADDS INFORMATION |
| over 2.5 | sharp close gap | 382 | 292 | 0.2427 | +0.00775 | 0.00430 | NO CLEAR EFFECT |
| over 2.5 | Betfair close gap | 385 | 296 | 0.2437 | +0.00630 | 0.00256 | ADDS INFORMATION |
| BTTS yes | xG total | 178 | 125 | 0.2393 | -0.00125 | 0.00066 | NO CLEAR EFFECT |
| BTTS yes | soft close gap | 607 | 480 | 0.2451 | +0.00173 | 0.00202 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 382 | 292 | 0.2388 | -0.00195 | 0.00375 | NO CLEAR EFFECT |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
