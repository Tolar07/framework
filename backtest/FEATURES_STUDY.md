# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

763 fixtures, 2026-10-04 to 2026-10-30.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 763 |
| with xG form (both teams, 2+ prior matches) | 237 |
| with team news | 638 |
| with confirmed lineups | 296 |
| with SportyBet close | 685 |
| with Matchbook (sharp) close | 460 |
| with Betfair Exchange close | 415 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 237 | 184 | 0.2183 | -0.00064 | 0.00112 | NO CLEAR EFFECT |
| home win | team-news edge | 638 | 529 | 0.2216 | -0.00142 | 0.00184 | NO CLEAR EFFECT |
| home win | soft close gap | 685 | 558 | 0.2238 | +0.00331 | 0.00253 | NO CLEAR EFFECT |
| home win | sharp close gap | 460 | 370 | 0.2222 | +0.00153 | 0.00359 | NO CLEAR EFFECT |
| home win | Betfair close gap | 415 | 326 | 0.2234 | +0.00670 | 0.00393 | NO CLEAR EFFECT |
| over 2.5 | xG total | 237 | 184 | 0.2348 | +0.00084 | 0.00085 | NO CLEAR EFFECT |
| over 2.5 | soft close gap | 685 | 558 | 0.2413 | +0.00317 | 0.00162 | NO CLEAR EFFECT |
| over 2.5 | sharp close gap | 460 | 370 | 0.2390 | +0.00463 | 0.00379 | NO CLEAR EFFECT |
| over 2.5 | Betfair close gap | 415 | 326 | 0.2388 | +0.00504 | 0.00249 | ADDS INFORMATION |
| BTTS yes | xG total | 237 | 184 | 0.2332 | -0.00027 | 0.00061 | NO CLEAR EFFECT |
| BTTS yes | soft close gap | 685 | 558 | 0.2427 | +0.00081 | 0.00190 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 457 | 367 | 0.2354 | -0.00314 | 0.00324 | NO CLEAR EFFECT |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
