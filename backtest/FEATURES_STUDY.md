# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

959 fixtures, 2026-10-04 to 2026-11-02.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 959 |
| with xG form (both teams, 2+ prior matches) | 398 |
| with team news | 817 |
| with confirmed lineups | 474 |
| with SportyBet close | 867 |
| with Matchbook (sharp) close | 636 |
| with Betfair Exchange close | 539 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 398 | 345 | 0.2237 | +0.00028 | 0.00079 | NO CLEAR EFFECT |
| home win | team-news edge | 817 | 708 | 0.2250 | -0.00113 | 0.00146 | NO CLEAR EFFECT |
| home win | soft close gap | 867 | 740 | 0.2256 | +0.00465 | 0.00220 | ADDS INFORMATION |
| home win | sharp close gap | 636 | 546 | 0.2256 | +0.00395 | 0.00291 | NO CLEAR EFFECT |
| home win | Betfair close gap | 539 | 450 | 0.2340 | +0.00787 | 0.00343 | ADDS INFORMATION |
| over 2.5 | xG total | 398 | 345 | 0.2432 | +0.00051 | 0.00102 | NO CLEAR EFFECT |
| over 2.5 | soft close gap | 867 | 740 | 0.2439 | +0.00393 | 0.00163 | ADDS INFORMATION |
| over 2.5 | sharp close gap | 636 | 546 | 0.2433 | +0.00558 | 0.00321 | NO CLEAR EFFECT |
| over 2.5 | Betfair close gap | 539 | 450 | 0.2441 | +0.00499 | 0.00248 | ADDS INFORMATION |
| BTTS yes | xG total | 398 | 345 | 0.2409 | +0.00082 | 0.00091 | NO CLEAR EFFECT |
| BTTS yes | soft close gap | 867 | 740 | 0.2447 | +0.00159 | 0.00165 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 633 | 543 | 0.2403 | -0.00131 | 0.00245 | NO CLEAR EFFECT |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
