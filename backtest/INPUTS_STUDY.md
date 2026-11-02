# INPUTS STUDY — head-to-head, form and last-5 xG beyond the current model

Written by `backtest/inputs_study.py` (Architect 2026-10-28). Walk-forward: each feature's weight is fitted on earlier days only and the day is scored with and without it. Gain > 0 means the feature helped; a verdict needs 100+ scored matches and 2 standard errors. CLV: the bets each version takes at chance x opening >= 1.03, opening / closing - 1.

## A. Head-to-head and form — football-data, current Dixon-Coles model (3783 test matches, 3549 with a past meeting, 14 league-seasons)

| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict (Brier / log loss) | CLV model (bets) | CLV with feature (bets) |
|---|---|---|---|---|---|---|---|
| home win | h2h_gd | 3504 | 0.2214 | -0.00019 ± 0.00022 | -0.00061 ± 0.00053 | NO CLEAR EFFECT / NO CLEAR EFFECT | -0.81% (941) | -0.67% (921) |
| home win | h2h_goals | 3504 | 0.2214 | -0.00022 ± 0.00010 | -0.00056 ± 0.00023 | HURTS / HURTS | -0.81% (941) | -0.83% (942) |
| home win | form_ppg | 3738 | 0.2226 | -0.00038 ± 0.00018 | -0.00074 ± 0.00042 | HURTS / NO CLEAR EFFECT | -0.75% (1024) | -0.69% (1049) |
| home win | form_gd | 3738 | 0.2226 | -0.00042 ± 0.00014 | -0.00089 ± 0.00034 | HURTS / HURTS | -0.75% (1024) | -0.72% (1032) |
| home win | form_venue_ppg | 3738 | 0.2226 | -0.00019 ± 0.00009 | -0.00046 ± 0.00022 | HURTS / HURTS | -0.75% (1024) | -0.76% (1026) |
| home win | form_goals | 3738 | 0.2226 | -0.00034 ± 0.00030 | -0.00072 ± 0.00067 | NO CLEAR EFFECT / NO CLEAR EFFECT | -0.75% (1024) | -0.78% (1053) |
| over 2.5 | h2h_gd | 3504 | 0.2509 | -0.00029 ± 0.00028 | -0.00066 ± 0.00061 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.14% (633) | +0.13% (640) |
| over 2.5 | h2h_goals | 3504 | 0.2509 | +0.00074 ± 0.00083 | +0.00171 ± 0.00176 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.14% (633) | +0.28% (703) |
| over 2.5 | form_ppg | 3738 | 0.251 | -0.00012 ± 0.00039 | -0.00046 ± 0.00085 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.13% (685) | +0.19% (757) |
| over 2.5 | form_gd | 3738 | 0.251 | -0.00019 ± 0.00027 | -0.00047 ± 0.00059 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.13% (685) | +0.25% (732) |
| over 2.5 | form_venue_ppg | 3738 | 0.251 | -0.00028 ± 0.00020 | -0.00069 ± 0.00044 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.13% (685) | +0.16% (714) |
| over 2.5 | form_goals | 3738 | 0.251 | +0.00029 ± 0.00060 | +0.00082 ± 0.00128 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.13% (685) | -0.05% (699) |

## B. Last-5 xG — the board's rated fixtures (938 graded, 513 with 3+ studied matches a side)

| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict |
|---|---|---|---|---|---|
| home win | xG edge | 431 | 0.2224 | +0.00146 ± 0.00215 | +0.00335 ± 0.00479 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| over 2.5 | xG total | 431 | 0.2411 | -0.00036 ± 0.00210 | -0.00147 ± 0.00484 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| BTTS yes | xG total | 431 | 0.2403 | -0.00024 ± 0.00065 | -0.00055 ± 0.00139 | NO CLEAR EFFECT / NO CLEAR EFFECT |

## C. Lineups / injuries — share of the best XI unavailable (460 graded fixtures with news, of 990 on 23 days)

| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict |
|---|---|---|---|---|---|
| home win | missing edge | 414 | 0.226 | -0.00109 ± 0.00181 | -0.00219 ± 0.00389 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| away win | missing edge | 414 | 0.187 | -0.00132 ± 0.00084 | -0.00317 ± 0.00204 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| over 2.5 | missing total | 414 | 0.2405 | +0.00153 ± 0.00296 | +0.00320 ± 0.00621 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| BTTS yes | missing total | 414 | 0.243 | -0.00601 ± 0.00362 | -0.01420 ± 0.00828 | NO CLEAR EFFECT / NO CLEAR EFFECT |

## Verdict

No candidate input improves the model out of sample on both Brier and log loss: none goes live.

A feature that adds information to the probability is still not an edge: the CLV columns say whether the bets it changes beat the close.
