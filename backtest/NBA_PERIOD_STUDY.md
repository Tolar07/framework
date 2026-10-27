# NBA PERIOD STUDY — team totals, regulation total, half and quarter lines

ESPN regular seasons with the closing ESPN BET spread and total and all four quarter scores. **2023-24 learns every setting; 2024-25 and 2025-26 are the test.** Written by `backtest/nba_period_study.py`.

- 2023-24: 1231 games
- 2024-25: 1230 games
- 2025-26: 1229 games

## Q1 · Spread of real results around the closing line

Learned on 2023-24; the test column is the same measure on 2024-25 + 2025-26 (no refit). Close agreement = the setting holds out of sample.

| Quantity | Centre | sd (learn) | sd (test) | bias on test |
|---|---|---|---|---|
| Full-game margin | −S | 13.47 | 13.75 | -0.20 |
| Full-game total | T | 17.58 | 17.97 | +0.60 |
| Home points (227) | (T−S)/2 +0.18 | 11.07 | 11.34 | +0.02 |
| Away points (228) | (T+S)/2 +0.01 | 11.07 | 11.29 | +0.39 |
| Regulation total (18) | T -1.00 | 16.85 | 17.24 | +0.47 |
| 1st-half margin (66) | 0.639 × (−S) | 11.00 | 10.96 | -0.37 |
| 1st-quarter margin (303) | 0.331 × (−S) | 8.30 | 8.25 | -0.04 |
| 2nd-quarter margin (303) | 0.308 × (−S) | 8.24 | 8.25 | -0.34 |
| 3rd-quarter margin (303) | 0.320 × (−S) | 8.24 | 8.54 | -0.10 |
| 1st-half total | 0.501 × T | 11.96 | 11.88 | +0.39 |
| 1st-quarter total | 0.250 × T | 8.05 | 8.13 | +0.63 |

Overtime in 4.6% of test games (it counts in the full-game, team-total and handicap markets, never in the regulation total or a half/quarter).

## Q2 · Calibration on the test seasons

A line placed `offset` points above the centre (plus 0.5): the Over rate the Normal curve predicts with the LEARNED sd, against how often it landed.

**Home points** (sd 11.07)

| offset | predicted Over | landed |
|---|---|---|
| -9 | 77.9% | 76.4% |
| -6 | 69.0% | 68.4% |
| -3 | 58.9% | 59.1% |
| +0 | 48.2% | 47.9% |
| +3 | 37.6% | 37.0% |
| +6 | 27.9% | 28.7% |
| +9 | 19.5% | 19.9% |

**Regulation total** (sd 16.85)

| offset | predicted Over | landed |
|---|---|---|
| -9 | 69.3% | 68.1% |
| -6 | 62.8% | 61.9% |
| -3 | 55.9% | 55.3% |
| +0 | 48.8% | 49.2% |
| +3 | 41.8% | 42.3% |
| +6 | 35.0% | 35.2% |
| +9 | 28.6% | 28.6% |

**1st-half margin** (sd 11.00)

| offset | predicted Over | landed |
|---|---|---|
| -9 | 78.0% | 76.6% |
| -6 | 69.1% | 68.0% |
| -3 | 59.0% | 58.4% |
| +0 | 48.2% | 47.1% |
| +3 | 37.5% | 36.0% |
| +6 | 27.7% | 26.8% |
| +9 | 19.4% | 17.9% |

**Full-game margin** (sd 13.47)

| offset | predicted Over | landed |
|---|---|---|
| -9 | 73.6% | 73.4% |
| -6 | 65.9% | 65.5% |
| -3 | 57.4% | 57.0% |
| +0 | 48.5% | 47.2% |
| +3 | 39.7% | 37.1% |
| +6 | 31.5% | 29.4% |
| +9 | 24.0% | 22.0% |

## Q3 · Team quarter shares vs one league share (test seasons)

Each team's share of its own points in the period, season to date (half of last season carried in), shrunk with 20 games at the league share. Used only if it cuts the test error by 1% or more.

| Period line | RMSE league share | RMSE team shares | change | verdict |
|---|---|---|---|---|
| h1 margin | 10.96 | 11.00 | +0.4% | keep league share |
| h1 total | 11.88 | 11.80 | -0.7% | keep league share |
| q1 margin | 8.25 | 8.26 | +0.2% | keep league share |
| q1 total | 8.15 | 8.11 | -0.5% | keep league share |

## Settings for engine/nba_value.py

Centres and shares as learned on 2023-24. Each spread is the LARGER of the learn and test value: a curve a little too wide can only make the board see less value on the near-certain side of a far line, never more.

```
MARGIN_SD = 13.7
TOTAL_SD = 18.0
TEAM_SD = 11.3; HOME_B = +0.18; AWAY_B = +0.01
REG_B = -1.00; REG_SD = 17.2
H1_MARGIN = (0.639, 11.0)
Q1_MARGIN = (0.331, 8.3)
Q2_MARGIN = (0.308, 8.2)
Q3_MARGIN = (0.320, 8.5)
H1_TOTAL = (0.501, 12.0); Q1_TOTAL = (0.250, 8.1)
```

