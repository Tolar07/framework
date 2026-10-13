# GOALS LINE STUDY — the model's Over/Under 3.5 and 4.5 against results

Walk-forward (`backtest/goals_line_study.py`, method of `backtest/btts_study.py`): the model fitted only on matches before each 14-day block. STATE item 31 asked whether the board's match Unders run on an uncalibrated model. A study — nothing in the engine changes until the Architect says so.

## Over/Under 3.5 — 3598 matches

Model said Over 29.7% on average; landed 29.9%. So Under 70.3% said, 70.1% landed.

| Model's UNDER chance | matches | Under landed |
|---|---:|---:|
| 30%–40% | 35 | 42.9% |
| 40%–50% | 137 | 55.5% |
| 50%–60% | 456 | 65.1% |
| 60%–70% | 987 | 66.9% |
| 70%–80% | 1216 | 73.4% |
| 80%–90% | 691 | 75.7% |
| 90%–100% | 66 | 83.3% |

Platt fit on all 3598: a = -0.4096, b = 0.4947. Leave one league out: Brier 0.2087 → 0.2066, better in 11 of 13 leagues.

| Raw model Under | calibrated Under |
|---:|---:|
| 60% | 64.8% |
| 70% | 69.6% |
| 75% | 72.2% |
| 80% | 74.9% |
| 85% | 78.0% |
| 90% | 81.7% |

## Over/Under 4.5 — 3598 matches

Model said Over 15.2% on average; landed 13.6%. So Under 84.8% said, 86.4% landed.

| Model's UNDER chance | matches | Under landed |
|---|---:|---:|
| 50%–60% | 35 | 62.9% |
| 60%–70% | 160 | 73.1% |
| 70%–80% | 649 | 84.7% |
| 80%–90% | 1667 | 87.0% |
| 90%–100% | 1076 | 89.8% |

Platt fit on all 3598: a = -0.8932, b = 0.5389. Leave one league out: Brier 0.1169 → 0.1156, better in 10 of 13 leagues.

| Raw model Under | calibrated Under |
|---:|---:|
| 60% | 75.2% |
| 70% | 79.4% |
| 75% | 81.5% |
| 80% | 83.8% |
| 85% | 86.2% |
| 90% | 88.9% |

