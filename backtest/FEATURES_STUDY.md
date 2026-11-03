# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

954 fixtures, 2026-10-04 to 2026-11-02.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 954 |
| with xG form (both teams, 2+ prior matches) | 393 |
| with team news | 812 |
| with confirmed lineups | 469 |
| with SportyBet close | 863 |
| with Matchbook (sharp) close | 632 |
| with Betfair Exchange close | 529 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 393 | 340 | 0.2246 | +0.00035 | 0.00080 | NO CLEAR EFFECT |
| home win | team-news edge | 812 | 703 | 0.2254 | -0.00127 | 0.00147 | NO CLEAR EFFECT |
| home win | soft close gap | 863 | 736 | 0.2261 | +0.00450 | 0.00221 | ADDS INFORMATION |
| home win | sharp close gap | 632 | 542 | 0.2261 | +0.00371 | 0.00293 | NO CLEAR EFFECT |
| home win | Betfair close gap | 529 | 440 | 0.2347 | +0.00758 | 0.00345 | ADDS INFORMATION |
| over 2.5 | xG total | 393 | 340 | 0.2423 | +0.00054 | 0.00102 | NO CLEAR EFFECT |
| over 2.5 | soft close gap | 863 | 736 | 0.2436 | +0.00395 | 0.00162 | ADDS INFORMATION |
| over 2.5 | sharp close gap | 632 | 542 | 0.2428 | +0.00567 | 0.00321 | NO CLEAR EFFECT |
| over 2.5 | Betfair close gap | 529 | 440 | 0.2428 | +0.00433 | 0.00245 | NO CLEAR EFFECT |
| BTTS yes | xG total | 393 | 340 | 0.2403 | +0.00085 | 0.00090 | NO CLEAR EFFECT |
| BTTS yes | soft close gap | 863 | 736 | 0.2445 | +0.00152 | 0.00165 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 629 | 539 | 0.2399 | -0.00141 | 0.00245 | NO CLEAR EFFECT |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
