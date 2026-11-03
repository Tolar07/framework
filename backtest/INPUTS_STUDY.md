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
| home win | table_ppg_gap | 3276 | 0.2226 | -0.00049 ± 0.00039 | -0.00118 ± 0.00088 | NO CLEAR EFFECT / NO CLEAR EFFECT | -0.94% (922) | -0.96% (945) |
| home win | table_stakes | 1401 | 0.2159 | -0.00043 ± 0.00045 | -0.00117 ± 0.00105 | NO CLEAR EFFECT / NO CLEAR EFFECT | -0.74% (358) | -0.55% (345) |
| over 2.5 | h2h_gd | 3504 | 0.2509 | -0.00029 ± 0.00028 | -0.00066 ± 0.00061 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.14% (633) | +0.13% (640) |
| over 2.5 | h2h_goals | 3504 | 0.2509 | +0.00074 ± 0.00083 | +0.00171 ± 0.00176 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.14% (633) | +0.28% (703) |
| over 2.5 | form_ppg | 3738 | 0.251 | -0.00012 ± 0.00039 | -0.00046 ± 0.00085 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.13% (685) | +0.19% (757) |
| over 2.5 | form_gd | 3738 | 0.251 | -0.00019 ± 0.00027 | -0.00047 ± 0.00059 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.13% (685) | +0.25% (732) |
| over 2.5 | form_venue_ppg | 3738 | 0.251 | -0.00028 ± 0.00020 | -0.00069 ± 0.00044 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.13% (685) | +0.16% (714) |
| over 2.5 | form_goals | 3738 | 0.251 | +0.00029 ± 0.00060 | +0.00082 ± 0.00128 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.13% (685) | -0.05% (699) |
| over 2.5 | table_ppg_gap | 3276 | 0.2505 | -0.00035 ± 0.00024 | -0.00084 ± 0.00054 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.14% (582) | +0.24% (600) |
| over 2.5 | table_stakes | 1401 | 0.247 | -0.00110 ± 0.00054 | -0.00231 ± 0.00111 | HURTS / HURTS | +0.73% (209) | +0.67% (226) |

## B. Last-5 xG — the board's rated fixtures (959 graded, 522 with 3+ studied matches a side)

| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict |
|---|---|---|---|---|---|
| home win | xG edge | 440 | 0.2224 | +0.00147 ± 0.00212 | +0.00338 ± 0.00471 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| over 2.5 | xG total | 440 | 0.2427 | -0.00025 ± 0.00207 | -0.00127 ± 0.00475 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| BTTS yes | xG total | 440 | 0.2407 | -0.00022 ± 0.00064 | -0.00051 ± 0.00137 | NO CLEAR EFFECT / NO CLEAR EFFECT |

## C. Lineups / injuries — share of the best XI unavailable (473 graded fixtures with news, of 1012 on 24 days)

| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict |
|---|---|---|---|---|---|
| home win | missing edge | 427 | 0.2275 | -0.00106 ± 0.00176 | -0.00214 ± 0.00377 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| away win | missing edge | 427 | 0.1892 | -0.00128 ± 0.00082 | -0.00310 ± 0.00199 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| over 2.5 | missing total | 427 | 0.2415 | +0.00048 ± 0.00294 | +0.00098 ± 0.00616 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| BTTS yes | missing total | 427 | 0.2419 | -0.00638 ± 0.00353 | -0.01489 ± 0.00806 | NO CLEAR EFFECT / NO CLEAR EFFECT |

## Verdict

No candidate input improves the model out of sample on both Brier and log loss: none goes live.

A feature that adds information to the probability is still not an edge: the CLV columns say whether the bets it changes beat the close.
