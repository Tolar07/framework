# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

736 fixtures, 2026-10-04 to 2026-10-28.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 736 |
| with xG form (both teams, 2+ prior matches) | 212 |
| with team news | 611 |
| with confirmed lineups | 269 |
| with SportyBet close | 653 |
| with Matchbook (sharp) close | 428 |
| with Betfair Exchange close | 385 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 212 | 159 | 0.2149 | -0.00073 | 0.00129 | NO CLEAR EFFECT |
| home win | team-news edge | 611 | 502 | 0.2212 | -0.00160 | 0.00193 | NO CLEAR EFFECT |
| home win | soft close gap | 653 | 526 | 0.2229 | +0.00332 | 0.00251 | NO CLEAR EFFECT |
| home win | sharp close gap | 428 | 338 | 0.2207 | +0.00126 | 0.00353 | NO CLEAR EFFECT |
| home win | Betfair close gap | 385 | 296 | 0.2247 | +0.00621 | 0.00412 | NO CLEAR EFFECT |
| over 2.5 | xG total | 212 | 159 | 0.2397 | -0.00001 | 0.00086 | NO CLEAR EFFECT |
| over 2.5 | soft close gap | 653 | 526 | 0.2427 | +0.00384 | 0.00164 | ADDS INFORMATION |
| over 2.5 | sharp close gap | 428 | 338 | 0.2410 | +0.00640 | 0.00398 | NO CLEAR EFFECT |
| over 2.5 | Betfair close gap | 385 | 296 | 0.2437 | +0.00630 | 0.00256 | ADDS INFORMATION |
| BTTS yes | xG total | 212 | 159 | 0.2363 | -0.00085 | 0.00057 | NO CLEAR EFFECT |
| BTTS yes | soft close gap | 653 | 526 | 0.2436 | +0.00086 | 0.00191 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 425 | 335 | 0.2361 | -0.00332 | 0.00335 | NO CLEAR EFFECT |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
