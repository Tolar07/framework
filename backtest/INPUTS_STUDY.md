# INPUTS STUDY — head-to-head, form and last-5 xG beyond the current model

Written by `backtest/inputs_study.py` (Architect 2026-10-28). Walk-forward: each feature's weight is fitted on earlier days only and the day is scored with and without it. Gain > 0 means the feature helped; a verdict needs 100+ scored matches and 2 standard errors. CLV: the bets each version takes at chance x opening >= 1.03, opening / closing - 1.

## A. Head-to-head and form — football-data, current Dixon-Coles model (3717 test matches, 3506 with a past meeting, 14 league-seasons)

| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict (Brier / log loss) | CLV model (bets) | CLV with feature (bets) |
|---|---|---|---|---|---|---|---|
| home win | h2h_gd | 3461 | 0.2211 | -0.00019 ± 0.00022 | -0.00062 ± 0.00054 | NO CLEAR EFFECT / NO CLEAR EFFECT | -0.78% (929) | -0.63% (910) |
| home win | h2h_goals | 3461 | 0.2211 | -0.00022 ± 0.00010 | -0.00055 ± 0.00024 | HURTS / HURTS | -0.78% (929) | -0.80% (930) |
| home win | form_ppg | 3672 | 0.2222 | -0.00038 ± 0.00019 | -0.00073 ± 0.00042 | HURTS / NO CLEAR EFFECT | -0.71% (1001) | -0.64% (1027) |
| home win | form_gd | 3672 | 0.2222 | -0.00043 ± 0.00014 | -0.00090 ± 0.00034 | HURTS / HURTS | -0.71% (1001) | -0.67% (1009) |
| home win | form_venue_ppg | 3672 | 0.2222 | -0.00019 ± 0.00010 | -0.00044 ± 0.00022 | NO CLEAR EFFECT / NO CLEAR EFFECT | -0.71% (1001) | -0.72% (1004) |
| home win | form_goals | 3672 | 0.2222 | -0.00035 ± 0.00031 | -0.00074 ± 0.00068 | NO CLEAR EFFECT / NO CLEAR EFFECT | -0.71% (1001) | -0.74% (1030) |
| over 2.5 | h2h_gd | 3461 | 0.2503 | -0.00030 ± 0.00028 | -0.00068 ± 0.00062 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.16% (628) | +0.14% (633) |
| over 2.5 | h2h_goals | 3461 | 0.2503 | +0.00071 ± 0.00084 | +0.00163 ± 0.00177 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.16% (628) | +0.27% (698) |
| over 2.5 | form_ppg | 3672 | 0.2508 | -0.00010 ± 0.00040 | -0.00042 ± 0.00087 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.15% (675) | +0.21% (747) |
| over 2.5 | form_gd | 3672 | 0.2508 | -0.00019 ± 0.00028 | -0.00047 ± 0.00060 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.15% (675) | +0.27% (723) |
| over 2.5 | form_venue_ppg | 3672 | 0.2508 | -0.00029 ± 0.00020 | -0.00072 ± 0.00045 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.15% (675) | +0.17% (704) |
| over 2.5 | form_goals | 3672 | 0.2508 | +0.00028 ± 0.00061 | +0.00079 ± 0.00129 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.15% (675) | -0.03% (690) |

## B. Last-5 xG — the board's rated fixtures (715 graded, 392 with 3+ studied matches a side)

| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict |
|---|---|---|---|---|---|
| home win | xG edge | 310 | 0.2182 | +0.00205 ± 0.00260 | +0.00427 ± 0.00577 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| over 2.5 | xG total | 310 | 0.2371 | +0.00053 ± 0.00254 | +0.00120 ± 0.00573 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| BTTS yes | xG total | 310 | 0.239 | -0.00038 ± 0.00069 | -0.00085 ± 0.00145 | NO CLEAR EFFECT / NO CLEAR EFFECT |

## Verdict

No candidate input improves the model out of sample on both Brier and log loss: none goes live.

A feature that adds information to the probability is still not an edge: the CLV columns say whether the bets it changes beat the close.
