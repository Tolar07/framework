# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

461 fixtures, 2026-10-04 to 2026-10-21.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 461 |
| with xG form (both teams, 2+ prior matches) | 34 |
| with team news | 359 |
| with confirmed lineups | 23 |
| with SportyBet close | 395 |
| with Matchbook (sharp) close | 175 |
| with Betfair Exchange close | 253 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 34 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| home win | team-news edge | 359 | 250 | 0.2185 | +0.00110 | 0.00304 | NO CLEAR EFFECT |
| home win | soft close gap | 395 | 268 | 0.2217 | +0.00070 | 0.00352 | NO CLEAR EFFECT |
| home win | sharp close gap | 175 | 86 | 0.2168 | -0.01435 | 0.00766 | NOT ENOUGH DATA |
| home win | Betfair close gap | 253 | 164 | 0.2199 | +0.00430 | 0.00571 | NO CLEAR EFFECT |
| over 2.5 | xG total | 34 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| over 2.5 | soft close gap | 395 | 268 | 0.2433 | +0.00163 | 0.00159 | NO CLEAR EFFECT |
| over 2.5 | sharp close gap | 175 | 86 | 0.2373 | -0.00057 | 0.00920 | NOT ENOUGH DATA |
| over 2.5 | Betfair close gap | 253 | 164 | 0.2444 | +0.00350 | 0.00264 | NO CLEAR EFFECT |
| BTTS yes | xG total | 34 | 0 | PENDING | +0.00000 | 0.00000 | NOT ENOUGH DATA |
| BTTS yes | soft close gap | 395 | 268 | 0.2500 | +0.00004 | 0.00271 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 175 | 86 | 0.2392 | -0.01430 | 0.00996 | NOT ENOUGH DATA |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
