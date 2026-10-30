# INPUTS STUDY — head-to-head, form and last-5 xG beyond the current model

Written by `backtest/inputs_study.py` (Architect 2026-10-28). Walk-forward: each feature's weight is fitted on earlier days only and the day is scored with and without it. Gain > 0 means the feature helped; a verdict needs 100+ scored matches and 2 standard errors. CLV: the bets each version takes at chance x opening >= 1.03, opening / closing - 1.

## A. Head-to-head and form — football-data, current Dixon-Coles model (3735 test matches, 3516 with a past meeting, 14 league-seasons)

| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict (Brier / log loss) | CLV model (bets) | CLV with feature (bets) |
|---|---|---|---|---|---|---|---|
| home win | h2h_gd | 3471 | 0.2211 | -0.00020 ± 0.00022 | -0.00065 ± 0.00054 | NO CLEAR EFFECT / NO CLEAR EFFECT | -0.80% (933) | -0.65% (913) |
| home win | h2h_goals | 3471 | 0.2211 | -0.00022 ± 0.00010 | -0.00055 ± 0.00024 | HURTS / HURTS | -0.80% (933) | -0.82% (934) |
| home win | form_ppg | 3690 | 0.2221 | -0.00039 ± 0.00019 | -0.00074 ± 0.00042 | HURTS / NO CLEAR EFFECT | -0.74% (1008) | -0.67% (1032) |
| home win | form_gd | 3690 | 0.2221 | -0.00042 ± 0.00014 | -0.00090 ± 0.00034 | HURTS / HURTS | -0.74% (1008) | -0.70% (1015) |
| home win | form_venue_ppg | 3690 | 0.2221 | -0.00019 ± 0.00009 | -0.00045 ± 0.00022 | NO CLEAR EFFECT / HURTS | -0.74% (1008) | -0.75% (1010) |
| home win | form_goals | 3690 | 0.2221 | -0.00035 ± 0.00030 | -0.00073 ± 0.00067 | NO CLEAR EFFECT / NO CLEAR EFFECT | -0.74% (1008) | -0.77% (1038) |
| over 2.5 | h2h_gd | 3471 | 0.2502 | -0.00032 ± 0.00028 | -0.00071 ± 0.00062 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.16% (629) | +0.15% (636) |
| over 2.5 | h2h_goals | 3471 | 0.2502 | +0.00073 ± 0.00083 | +0.00168 ± 0.00177 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.16% (629) | +0.29% (697) |
| over 2.5 | form_ppg | 3690 | 0.2506 | -0.00011 ± 0.00040 | -0.00042 ± 0.00086 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.15% (678) | +0.21% (750) |
| over 2.5 | form_gd | 3690 | 0.2506 | -0.00019 ± 0.00028 | -0.00046 ± 0.00060 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.15% (678) | +0.26% (726) |
| over 2.5 | form_venue_ppg | 3690 | 0.2506 | -0.00029 ± 0.00020 | -0.00071 ± 0.00045 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.15% (678) | +0.17% (707) |
| over 2.5 | form_goals | 3690 | 0.2506 | +0.00023 ± 0.00060 | +0.00067 ± 0.00129 | NO CLEAR EFFECT / NO CLEAR EFFECT | +0.15% (678) | -0.04% (693) |

## B. Last-5 xG — the board's rated fixtures (741 graded, 408 with 3+ studied matches a side)

| outcome / feature | scored | Brier model | Brier gain ± se | log-loss gain ± se | verdict |
|---|---|---|---|---|---|
| home win | xG edge | 326 | 0.2169 | +0.00165 ± 0.00250 | +0.00334 ± 0.00557 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| over 2.5 | xG total | 326 | 0.2358 | +0.00103 ± 0.00246 | +0.00189 ± 0.00561 | NO CLEAR EFFECT / NO CLEAR EFFECT |
| BTTS yes | xG total | 326 | 0.2377 | -0.00019 ± 0.00067 | -0.00043 ± 0.00142 | NO CLEAR EFFECT / NO CLEAR EFFECT |

## Verdict

No candidate input improves the model out of sample on both Brier and log loss: none goes live.

A feature that adds information to the probability is still not an edge: the CLV columns say whether the bets it changes beat the close.
