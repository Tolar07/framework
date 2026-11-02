# NBA projection study — 2026-11-02

RECORDED ONLY (Architect 2026-10-28). The player-built projection (engine/nba_projection.py) against the sharp line and SportyBet, on games it was not fitted to. Nothing here feeds a pick.

Graded games with a board-time projection: **20** (line-up shock: 4).

## All games

### 1. Error against actual points (mean miss / bias, points)

| number | forecaster | n | mean miss | bias |
|---|---|---|---|---|
| total | projection | 20 | 16.8 | 3.9 |
| total | sharp board | 20 | 15.3 | 5.2 |
| total | sharp close | 20 | 15.3 | 4.2 |
| total | SportyBet | 20 | 15.4 | 5.2 |
| spread | projection | 20 | 13.8 | 3.5 |
| spread | sharp board | 20 | 12.2 | 3.1 |
| spread | sharp close | 20 | 12.7 | 3.7 |
| h1_total | projection | 20 | 11.0 | 1.6 |
| h1_total | sharp board | 20 | 10.4 | 2.2 |
| h1_total | sharp close | 20 | 10.2 | 1.8 |
| h1_total | SportyBet | 16 | 12.2 | 1.1 |
| q1_total | projection | 20 | 9.0 | 2.4 |
| q1_total | sharp board | 20 | 8.7 | 2.7 |
| q1_total | sharp close | 20 | 8.5 | 2.5 |
| q1_total | SportyBet | 14 | 9.4 | 0.6 |

### 2. Results — both sides of every recorded line (lower is better)

| forecaster | lines | Brier | log loss |
|---|---|---|---|
| projection | 130 | 0.2645 | 0.7246 |
| sharp | 130 | 0.2396 | 0.6721 |
| sharp_recal | 130 | 0.2396 | 0.6721 |

### 3. CLV — the projection's side at SportyBet's board total vs the sharp close

- games 20: mean 0.25 points toward the projection's side, positive 50%
- projection 4+ points off SportyBet: 8 games, mean 0.62 points
- projection 4+ points off the board-time sharp total: its side won 4, lost 4

## Line-up shock games

### 1. Error against actual points (mean miss / bias, points)

| number | forecaster | n | mean miss | bias |
|---|---|---|---|---|
| total | projection | 4 | 14.2 | 2.6 |
| total | sharp board | 4 | 11.5 | 4.0 |
| total | sharp close | 4 | 10.8 | 5.8 |
| total | SportyBet | 4 | 11.2 | 4.2 |
| spread | projection | 4 | 13.1 | -3.3 |
| spread | sharp board | 4 | 11.8 | -3.5 |
| spread | sharp close | 4 | 12.2 | -3.0 |
| h1_total | projection | 4 | 8.4 | -1.0 |
| h1_total | sharp board | 4 | 7.9 | -0.3 |
| h1_total | sharp close | 4 | 7.3 | 0.6 |
| h1_total | SportyBet | 3 | 13.2 | -0.8 |
| q1_total | projection | 4 | 6.4 | 0.2 |
| q1_total | sharp board | 4 | 6.2 | 0.6 |
| q1_total | sharp close | 4 | 5.9 | 1.0 |
| q1_total | SportyBet | 3 | 8.2 | 2.2 |

### 2. Results — both sides of every recorded line (lower is better)

| forecaster | lines | Brier | log loss |
|---|---|---|---|
| projection | 26 | 0.2676 | 0.7308 |
| sharp | 26 | 0.2307 | 0.6539 |
| sharp_recal | 26 | 0.2307 | 0.6539 |

### 3. CLV — the projection's side at SportyBet's board total vs the sharp close

- games 4: mean -1.00 points toward the projection's side, positive 25%
- projection 4+ points off SportyBet: 1 games, mean -4.00 points
- projection 4+ points off the board-time sharp total: its side won 0, lost 1

## Hindsight check (season log, line-ups known only afterwards — NOT a forecast)

- games 56: total mean miss projection 15.3 vs sharp close 14.6
- projection 4+ points off the sharp close: its side won 18, lost 13

## Projection gate (engine/nba_gate.py)

**closed** — 20 graded games < 150; does not beat the sharp line on both Brier and log loss. Recorded only until all hold.

