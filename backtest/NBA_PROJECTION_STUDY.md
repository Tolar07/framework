# NBA projection study — 2026-11-05

RECORDED ONLY (Architect 2026-10-28). The player-built projection (engine/nba_projection.py) against the sharp line and SportyBet, on games it was not fitted to. Nothing here feeds a pick.

Graded games with a board-time projection: **39** (line-up shock: 12).

## All games

### 1. Error against actual points (mean miss / bias, points)

| number | forecaster | n | mean miss | bias |
|---|---|---|---|---|
| total | projection | 39 | 17.5 | 4.8 |
| total | sharp board | 39 | 16.6 | 5.0 |
| total | sharp close | 39 | 16.4 | 4.0 |
| total | SportyBet | 39 | 16.7 | 5.0 |
| spread | projection | 39 | 11.5 | 0.3 |
| spread | sharp board | 39 | 10.6 | 0.1 |
| spread | sharp close | 39 | 10.9 | 0.8 |
| h1_total | projection | 39 | 11.2 | 1.6 |
| h1_total | sharp board | 39 | 10.6 | 1.6 |
| h1_total | sharp close | 39 | 10.5 | 1.1 |
| h1_total | SportyBet | 32 | 11.6 | 2.9 |
| q1_total | projection | 39 | 8.4 | 3.3 |
| q1_total | sharp board | 39 | 8.4 | 3.3 |
| q1_total | sharp close | 39 | 8.3 | 3.1 |
| q1_total | SportyBet | 30 | 9.3 | 3.0 |

### 2. Results — both sides of every recorded line (lower is better)

| forecaster | lines | Brier | log loss |
|---|---|---|---|
| projection | 257 | 0.2552 | 0.7055 |
| sharp | 257 | 0.2416 | 0.6761 |
| sharp_recal | 257 | 0.2416 | 0.6761 |

### 3. CLV — the projection's side at SportyBet's board total vs the sharp close

- games 39: mean 0.08 points toward the projection's side, positive 44%
- projection 4+ points off SportyBet: 17 games, mean 0.24 points
- projection 4+ points off the board-time sharp total: its side won 10, lost 7

## Line-up shock games

### 1. Error against actual points (mean miss / bias, points)

| number | forecaster | n | mean miss | bias |
|---|---|---|---|---|
| total | projection | 12 | 14.3 | 0.8 |
| total | sharp board | 12 | 14.2 | -0.1 |
| total | sharp close | 12 | 13.6 | 0.1 |
| total | SportyBet | 12 | 14.0 | 0.1 |
| spread | projection | 12 | 8.1 | -0.9 |
| spread | sharp board | 12 | 6.8 | -1.1 |
| spread | sharp close | 12 | 6.9 | -0.6 |
| h1_total | projection | 12 | 8.5 | 2.8 |
| h1_total | sharp board | 12 | 8.5 | 2.4 |
| h1_total | sharp close | 12 | 8.2 | 2.5 |
| h1_total | SportyBet | 10 | 11.4 | 2.8 |
| q1_total | projection | 12 | 7.1 | 3.3 |
| q1_total | sharp board | 12 | 7.0 | 3.1 |
| q1_total | sharp close | 12 | 6.8 | 3.1 |
| q1_total | SportyBet | 10 | 8.7 | 3.7 |

### 2. Results — both sides of every recorded line (lower is better)

| forecaster | lines | Brier | log loss |
|---|---|---|---|
| projection | 80 | 0.2487 | 0.6925 |
| sharp | 80 | 0.2387 | 0.6703 |
| sharp_recal | 80 | 0.2387 | 0.6703 |

### 3. CLV — the projection's side at SportyBet's board total vs the sharp close

- games 12: mean -0.17 points toward the projection's side, positive 33%
- projection 4+ points off SportyBet: 6 games, mean 0.00 points
- projection 4+ points off the board-time sharp total: its side won 4, lost 2

## Hindsight check (season log, line-ups known only afterwards — NOT a forecast)

- games 74: total mean miss projection 16.0 vs sharp close 15.3
- projection 4+ points off the sharp close: its side won 23, lost 15

## Projection gate (engine/nba_gate.py)

**closed** — 39 graded games < 150; does not beat the sharp line on both Brier and log loss. Recorded only until all hold.

