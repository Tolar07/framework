# NBA projection study — 2026-11-03

RECORDED ONLY (Architect 2026-10-28). The player-built projection (engine/nba_projection.py) against the sharp line and SportyBet, on games it was not fitted to. Nothing here feeds a pick.

Graded games with a board-time projection: **24** (line-up shock: 7).

## All games

### 1. Error against actual points (mean miss / bias, points)

| number | forecaster | n | mean miss | bias |
|---|---|---|---|---|
| total | projection | 24 | 18.8 | 4.9 |
| total | sharp board | 24 | 17.2 | 4.9 |
| total | sharp close | 24 | 17.2 | 4.0 |
| total | SportyBet | 24 | 17.2 | 5.0 |
| spread | projection | 24 | 12.7 | 2.4 |
| spread | sharp board | 24 | 11.3 | 2.3 |
| spread | sharp close | 24 | 11.8 | 3.0 |
| h1_total | projection | 24 | 11.7 | 2.8 |
| h1_total | sharp board | 24 | 10.9 | 2.8 |
| h1_total | sharp close | 24 | 10.8 | 2.4 |
| h1_total | SportyBet | 20 | 13.1 | 2.0 |
| q1_total | projection | 24 | 9.3 | 2.9 |
| q1_total | sharp board | 24 | 9.0 | 3.0 |
| q1_total | sharp close | 24 | 8.8 | 2.7 |
| q1_total | SportyBet | 18 | 9.9 | 1.3 |

### 2. Results — both sides of every recorded line (lower is better)

| forecaster | lines | Brier | log loss |
|---|---|---|---|
| projection | 158 | 0.2670 | 0.7300 |
| sharp | 158 | 0.2376 | 0.6680 |
| sharp_recal | 158 | 0.2376 | 0.6680 |

### 3. CLV — the projection's side at SportyBet's board total vs the sharp close

- games 24: mean 0.08 points toward the projection's side, positive 46%
- projection 4+ points off SportyBet: 11 games, mean 0.45 points
- projection 4+ points off the board-time sharp total: its side won 5, lost 6

## Line-up shock games

### 1. Error against actual points (mean miss / bias, points)

| number | forecaster | n | mean miss | bias |
|---|---|---|---|---|
| total | projection | 7 | 17.7 | 0.1 |
| total | sharp board | 7 | 15.5 | -1.6 |
| total | sharp close | 7 | 15.2 | -1.1 |
| total | SportyBet | 7 | 15.4 | -1.5 |
| spread | projection | 7 | 9.7 | -1.5 |
| spread | sharp board | 7 | 8.9 | -1.1 |
| spread | sharp close | 7 | 9.5 | -0.5 |
| h1_total | projection | 7 | 8.3 | -0.6 |
| h1_total | sharp board | 7 | 7.7 | -1.4 |
| h1_total | sharp close | 7 | 7.4 | -1.2 |
| h1_total | SportyBet | 6 | 11.8 | -2.5 |
| q1_total | projection | 7 | 6.9 | 0.4 |
| q1_total | sharp board | 7 | 6.6 | -0.1 |
| q1_total | sharp close | 7 | 6.4 | 0.1 |
| q1_total | SportyBet | 6 | 8.5 | 0.2 |

### 2. Results — both sides of every recorded line (lower is better)

| forecaster | lines | Brier | log loss |
|---|---|---|---|
| projection | 47 | 0.2638 | 0.7243 |
| sharp | 47 | 0.2288 | 0.6500 |
| sharp_recal | 47 | 0.2288 | 0.6500 |

### 3. CLV — the projection's side at SportyBet's board total vs the sharp close

- games 7: mean -1.00 points toward the projection's side, positive 29%
- projection 4+ points off SportyBet: 3 games, mean -1.33 points
- projection 4+ points off the board-time sharp total: its side won 1, lost 2

## Hindsight check (season log, line-ups known only afterwards — NOT a forecast)

- games 60: total mean miss projection 16.1 vs sharp close 15.3
- projection 4+ points off the sharp close: its side won 19, lost 14

## Projection gate (engine/nba_gate.py)

**closed** — 24 graded games < 150; does not beat the sharp line on both Brier and log loss. Recorded only until all hold.

