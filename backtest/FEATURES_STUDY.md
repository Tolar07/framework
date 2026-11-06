# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

977 fixtures, 2026-10-04 to 2026-11-04.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 977 |
| with xG form (both teams, 2+ prior matches) | 415 |
| with team news | 834 |
| with confirmed lineups | 491 |
| with SportyBet close | 884 |
| with Matchbook (sharp) close | 652 |
| with Betfair Exchange close | 552 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 415 | 362 | 0.2221 | +0.00015 | 0.00080 | NO CLEAR EFFECT |
| home win | team-news edge | 834 | 725 | 0.2242 | -0.00110 | 0.00143 | NO CLEAR EFFECT |
| home win | soft close gap | 884 | 757 | 0.2249 | +0.00400 | 0.00219 | NO CLEAR EFFECT |
| home win | sharp close gap | 652 | 562 | 0.2247 | +0.00294 | 0.00288 | NO CLEAR EFFECT |
| home win | Betfair close gap | 552 | 463 | 0.2333 | +0.00787 | 0.00336 | ADDS INFORMATION |
| over 2.5 | xG total | 415 | 362 | 0.2443 | +0.00003 | 0.00099 | NO CLEAR EFFECT |
| over 2.5 | soft close gap | 884 | 757 | 0.2445 | +0.00410 | 0.00161 | ADDS INFORMATION |
| over 2.5 | sharp close gap | 652 | 562 | 0.2440 | +0.00582 | 0.00315 | NO CLEAR EFFECT |
| over 2.5 | Betfair close gap | 552 | 463 | 0.2451 | +0.00559 | 0.00246 | ADDS INFORMATION |
| BTTS yes | xG total | 415 | 362 | 0.2412 | +0.00033 | 0.00091 | NO CLEAR EFFECT |
| BTTS yes | soft close gap | 884 | 757 | 0.2448 | +0.00147 | 0.00163 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 649 | 559 | 0.2404 | -0.00135 | 0.00240 | NO CLEAR EFFECT |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
