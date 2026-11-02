# FEATURES STUDY — does the richer data add information beyond the model?

Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on earlier days only (from 40 rows), then the day is scored with and without it. **gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), ± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. The close gaps use the last price before kick-off, so they measure what the market knew that the model didn't. A study, not a selector: nothing here changes a pick.

938 fixtures, 2026-10-04 to 2026-11-01.

## Coverage

| Data | fixtures |
|---|---|
| graded model-rated fixtures | 938 |
| with xG form (both teams, 2+ prior matches) | 380 |
| with team news | 799 |
| with confirmed lineups | 456 |
| with SportyBet close | 847 |
| with Matchbook (sharp) close | 618 |
| with Betfair Exchange close | 415 |

## Walk-forward result

| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |
|---|---|---|---|---|---|---|---|
| home win | xG edge | 380 | 327 | 0.2226 | +0.00032 | 0.00079 | NO CLEAR EFFECT |
| home win | team-news edge | 799 | 690 | 0.2245 | -0.00130 | 0.00149 | NO CLEAR EFFECT |
| home win | soft close gap | 847 | 720 | 0.2251 | +0.00404 | 0.00222 | NO CLEAR EFFECT |
| home win | sharp close gap | 618 | 528 | 0.2247 | +0.00307 | 0.00294 | NO CLEAR EFFECT |
| home win | Betfair close gap | 415 | 326 | 0.2234 | +0.00670 | 0.00393 | NO CLEAR EFFECT |
| over 2.5 | xG total | 380 | 327 | 0.2411 | +0.00025 | 0.00105 | NO CLEAR EFFECT |
| over 2.5 | soft close gap | 847 | 720 | 0.2429 | +0.00352 | 0.00161 | ADDS INFORMATION |
| over 2.5 | sharp close gap | 618 | 528 | 0.2421 | +0.00513 | 0.00323 | NO CLEAR EFFECT |
| over 2.5 | Betfair close gap | 415 | 326 | 0.2388 | +0.00504 | 0.00249 | ADDS INFORMATION |
| BTTS yes | xG total | 380 | 327 | 0.2416 | +0.00072 | 0.00090 | NO CLEAR EFFECT |
| BTTS yes | soft close gap | 847 | 720 | 0.2447 | +0.00160 | 0.00165 | NO CLEAR EFFECT |
| BTTS yes | sharp close gap | 615 | 525 | 0.2402 | -0.00121 | 0.00247 | NO CLEAR EFFECT |

NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started 2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. The study reruns every morning (universe sweep) and the research harness reads it.
