# INPUTS STUDY — head-to-head, form and last-5 xG beyond the current model

Written by `backtest/inputs_study.py` (Architect 2026-10-28). Walk-forward: each feature's weight is fitted on earlier days only and the day is scored with and without it. Gain > 0 means the feature helped; a verdict needs 100+ scored matches and 2 standard errors. CLV: the bets each version takes at chance x opening >= 1.03, opening / closing - 1.

## A. Head-to-head and form — football-data, current Dixon-Coles model (3797 test matches, 3559 with a past meeting, 14 league-seasons)

| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict (Brier / log loss) | CLV model (bets) | CLV with feature (bets) |
|---|---|---|---|---|---|---|---|
| home win | h2h_gd | 3514 | 0.2215 | -0.00018 ± 0.00022 | -0.00059 ± 0.00053 | NO CLEAR EFFECT / NO CLEAR EFFECT | -0.81% (942) | -0.67% (921) |
| home win | h2h_goals | 3514 | 0.2215 | -0.00022 ± 0.00010 | -0.00055 ± 0.00023 | HURTS / HURTS | -0.81% (942) | -0.84% (943) |
| home win | form_ppg | 3752 | 0.2225 | -0.00038 ± 0.00018 | -0.00074 ± 0.00042 | HURTS / NO CLEAR EFFECT | -0.76% (1025) | -0.70% (1051) |
| home win | form_gd | 3752 | 0.2225 | -0.00042 ± 0.00014 | -0.00089 ± 0.00034 | HURTS / HURTS | -0.76% (1025) | -0.72% (1032) |
| home win | form_venue_ppg | 3752 | 0.2225 | -0.00019 ± 0.00009 | -0.00046 ± 0.00022 | HURTS / HURTS | -0.76% (1025) | -0.77% (1028) |
| home win | form_goals | 3752 | 0.2225 | -0.00034 ± 0.00030 | -0.00072 ± 0.00066 | NO CLEAR EFFECT / NO CLEAR EFFECT | -0.76% (1025) | -0.79% (1054) |
| home win | table_ppg_gap | 3290 | 0.2225 | -0.00049 ± 0.00039 | -0.00118 ± 0.00087 | NO CLEAR EFFECT / NO CLEAR EFFECT | -0.95% (923) | -0.97% (947) |
| home win | table_stakes | 1401 | 0.2159 | -0.00043 ± 0.00045 | -0.00117 ± 0.00105 | NO CLEAR EFFECT / NO CLEAR EFFECT | -0.74% (358) | -0.55% (345) |
| over 2.5 | h2h_gd | 3514 | 0.2509 | -0.00028 ± 0.00028 | -0.00064 ± 0.00061 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.12% (635) | +0.11% (642) |
| over 2.5 | h2h_goals | 3514 | 0.2509 | +0.00074 ± 0.00083 | +0.00171 ± 0.00175 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.12% (635) | +0.27% (704) |
| over 2.5 | form_ppg | 3752 | 0.251 | -0.00013 ± 0.00039 | -0.00047 ± 0.00085 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.11% (688) | +0.17% (760) |
| over 2.5 | form_gd | 3752 | 0.251 | -0.00019 ± 0.00027 | -0.00047 ± 0.00059 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.11% (688) | +0.23% (735) |
| over 2.5 | form_venue_ppg | 3752 | 0.251 | -0.00028 ± 0.00020 | -0.00069 ± 0.00044 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.11% (688) | +0.14% (715) |
| over 2.5 | form_goals | 3752 | 0.251 | +0.00035 ± 0.00060 | +0.00093 ± 0.00127 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.11% (688) | -0.05% (701) |
| over 2.5 | table_ppg_gap | 3290 | 0.2504 | -0.00035 ± 0.00024 | -0.00085 ± 0.00053 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.11% (585) | +0.24% (602) |
| over 2.5 | table_stakes | 1401 | 0.247 | -0.00110 ± 0.00054 | -0.00231 ± 0.00111 | HURTS / HURTS | +0.73% (209) | +0.67% (226) |

## B. Last-5 xG — the board's rated fixtures (972 graded, 531 with 3+ studied matches a side)

| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict |
|---|---|---|---|---|---|
| home win | xG edge | 449 | 0.222 | +0.00146 ± 0.00208 | +0.00346 ± 0.00463 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| over 2.5 | xG total | 449 | 0.2433 | -0.00062 ± 0.00203 | -0.00201 ± 0.00467 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| BTTS yes | xG total | 449 | 0.241 | -0.00033 ± 0.00063 | -0.00073 ± 0.00136 | NO CLEAR EFFECT / NO CLEAR EFFECT |

## C. Lineups / injuries — share of the best XI unavailable (478 graded fixtures with news, of 1027 on 25 days)

| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict | Brier on rows with a sharp close: model / with feature / sharp close (rows) | CLV |
|---|---|---|---|---|---|---|---|
| home win | missing edge | 432 | 0.2268 | -0.00115 ± 0.00174 | -0.00233 ± 0.00373 | NO CLEAR EFFECT / NO CLEAR EFFECT | 0.2276 / 0.2285 / 0.2194 (408) | PENDING (features hold the close only) |
| away win | missing edge | 432 | 0.1885 | -0.00133 ± 0.00081 | -0.00324 ± 0.00197 | NO CLEAR EFFECT / NO CLEAR EFFECT | 0.189 / 0.1903 / 0.1841 (408) | PENDING (features hold the close only) |
| over 2.5 | missing total | 432 | 0.2422 | +0.00043 ± 0.00293 | +0.00084 ± 0.00614 | NO CLEAR EFFECT / NO CLEAR EFFECT | 0.242 / 0.243 / 0.2342 (408) | PENDING (features hold the close only) |
| BTTS yes | missing total | 432 | 0.2424 | -0.00637 ± 0.00350 | -0.01488 ± 0.00798 | NO CLEAR EFFECT / NO CLEAR EFFECT | 0.2406 / 0.2434 / 0.2386 (405) | PENDING (features hold the close only) |

## Verdict

No candidate input improves the model out of sample on both Brier and log loss: none goes live.

A feature that adds information to the probability is still not an edge: the CLV columns say whether the bets it changes beat the close.
