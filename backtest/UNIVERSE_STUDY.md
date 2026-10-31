# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

8820 games graded (71% of 12443 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-31.

## Football — 7324 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 7184 | 31.9% | 32.4% | -0.5% | -12.8% ± 1.8% |
| 1x2:draw | 7184 | 23.3% | 24.6% | -1.3% | -14.5% ± 1.9% |
| 1x2:home | 7184 | 44.8% | 43.0% | +1.8% | -4.4% ± 1.6% |
| btts:no | 6148 | 44.3% | 45.8% | -1.5% | -11.1% ± 1.3% |
| btts:yes | 6148 | 55.7% | 54.2% | +1.5% | -5.6% ± 1.1% |
| dc:12 | 6859 | 76.8% | 74.6% | +2.3% | -4.8% ± 0.6% |
| dc:1x | 6859 | 68.0% | 67.5% | +0.5% | -8.6% ± 0.8% |
| dc:x2 | 6859 | 55.2% | 58.0% | -2.8% | -14.1% ± 1.0% |
| o/u1.5:over | 5482 | 76.7% | 74.6% | +2.1% | -3.9% ± 0.7% |
| o/u1.5:under | 5482 | 23.3% | 25.4% | -2.1% | -15.5% ± 2.2% |
| o/u2.5:over | 6769 | 56.2% | 54.1% | +2.2% | -3.3% ± 1.1% |
| o/u2.5:under | 6769 | 43.8% | 45.9% | -2.2% | -11.9% ± 1.3% |
| o/u3.5:over | 6204 | 37.1% | 36.2% | +0.9% | -5.6% ± 1.6% |
| o/u3.5:under | 6204 | 62.9% | 63.8% | -0.9% | -8.5% ± 0.9% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 586 | 83.6% | 78.5% | +5.2% | -1.5% ± 1.8% |
| 1x2 @ 1.30–1.60 | 1359 | 67.6% | 63.6% | +4.0% | -1.8% ± 1.9% |
| 1x2 @ 1.60–2.00 | 2136 | 54.2% | 51.6% | +2.6% | -3.2% ± 1.9% |
| 1x2 @ 2.00–3.00 | 5234 | 38.7% | 37.8% | +1.0% | -5.7% ± 1.7% |
| 1x2 @ 3.00–5.00 | 9484 | 24.0% | 25.4% | -1.4% | -13.3% ± 1.6% |
| 1x2 @ 5.00–1000.00 | 2753 | 11.4% | 13.5% | -2.1% | -22.5% ± 4.4% |
| btts @ 1.00–1.30 | 108 | 73.1% | 73.2% | -0.1% | -9.1% ± 5.3% |
| btts @ 1.30–1.60 | 2550 | 61.1% | 61.6% | -0.5% | -9.2% ± 1.4% |
| btts @ 1.60–2.00 | 5647 | 51.4% | 51.4% | +0.1% | -8.5% ± 1.2% |
| btts @ 2.00–3.00 | 3825 | 40.7% | 40.6% | +0.1% | -7.9% ± 1.8% |
| btts @ 3.00–5.00 | 166 | 30.1% | 27.9% | +2.2% | -0.5% ± 11.9% |
| dc @ 1.00–1.30 | 9459 | 80.6% | 77.4% | +3.2% | -3.8% ± 0.5% |
| dc @ 1.30–1.60 | 6445 | 66.0% | 66.2% | -0.2% | -7.8% ± 0.8% |
| dc @ 1.60–2.00 | 2550 | 47.6% | 52.9% | -5.3% | -16.9% ± 1.7% |
| dc @ 2.00–3.00 | 1634 | 34.2% | 40.1% | -5.9% | -21.4% ± 2.7% |
| dc @ 3.00–5.00 | 444 | 15.1% | 26.3% | -11.2% | -46.2% ± 6.1% |
| dc @ 5.00–1000.00 | 45 | 4.4% | 16.4% | -12.0% | -76.7% ± 16.3% |
| o/u1.5 @ 1.00–1.30 | 3692 | 80.8% | 78.5% | +2.3% | -3.6% ± 0.8% |
| o/u1.5 @ 1.30–1.60 | 1682 | 68.8% | 67.3% | +1.6% | -4.9% ± 1.6% |
| o/u1.5 @ 1.60–2.00 | 129 | 60.5% | 54.3% | +6.2% | +3.3% ± 7.4% |
| o/u1.5 @ 2.00–3.00 | 1061 | 33.8% | 35.8% | -2.0% | -12.8% ± 3.8% |
| o/u1.5 @ 3.00–5.00 | 3417 | 22.7% | 24.8% | -2.1% | -14.4% ± 2.7% |
| o/u1.5 @ 5.00–1000.00 | 983 | 12.9% | 15.8% | -2.9% | -23.4% ± 6.5% |
| o/u2.5 @ 1.00–1.30 | 267 | 79.8% | 75.6% | +4.2% | -1.4% ± 3.1% |
| o/u2.5 @ 1.30–1.60 | 2762 | 64.6% | 63.3% | +1.3% | -5.0% ± 1.3% |
| o/u2.5 @ 1.60–2.00 | 5331 | 53.1% | 52.3% | +0.8% | -5.8% ± 1.2% |
| o/u2.5 @ 2.00–3.00 | 4597 | 39.3% | 40.7% | -1.4% | -10.1% ± 1.7% |
| o/u2.5 @ 3.00–5.00 | 554 | 23.5% | 27.9% | -4.4% | -20.9% ± 6.1% |
| o/u3.5 @ 1.00–1.30 | 1423 | 76.5% | 75.7% | +0.7% | -6.4% ± 1.4% |
| o/u3.5 @ 1.30–1.60 | 3227 | 64.5% | 65.1% | -0.5% | -7.5% ± 1.2% |
| o/u3.5 @ 1.60–2.00 | 2071 | 53.5% | 53.0% | +0.5% | -5.7% ± 1.9% |
| o/u3.5 @ 2.00–3.00 | 3524 | 39.2% | 38.7% | +0.5% | -5.1% ± 2.0% |
| o/u3.5 @ 3.00–5.00 | 2062 | 25.9% | 26.6% | -0.7% | -9.5% ± 3.4% |
| o/u3.5 @ 5.00–1000.00 | 101 | 9.9% | 16.6% | -6.7% | -46.0% ± 16.3% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Algeria · Ligue 2 — 1x2:home | 41 | 73.2% | 50.8% | +22.3% | +28.7% ± 14.3% |
| Thailand · Thai League 2 — dc:1x | 33 | 87.9% | 69.6% | +18.3% | +18.0% ± 8.3% |
| Japan · J3 League — dc:12 | 32 | 90.6% | 72.6% | +18.0% | +15.6% ± 6.7% |
| Simulated Reality League · Serie A SRL — o/u1.5:over | 35 | 91.4% | 75.2% | +16.2% | +14.9% ± 6.2% |
| Spain · Primera Federacion — dc:1x | 48 | 85.4% | 68.7% | +16.7% | +14.9% ± 7.2% |
| Portugal · Campeonato de Portugal — dc:1x | 47 | 61.7% | 69.7% | -8.0% | -19.5% ± 9.7% |
| USA · MLS — dc:12 | 63 | 63.5% | 75.9% | -12.4% | -21.1% ± 7.6% |
| Spain · Segunda Federacion — dc:12 | 100 | 62.0% | 71.7% | -9.7% | -21.5% ± 6.2% |
| Italy · Serie B — dc:1x | 39 | 59.0% | 69.2% | -10.2% | -21.7% ± 10.8% |
| Spain · Primera Federacion — dc:x2 | 48 | 50.0% | 60.0% | -10.0% | -23.1% ± 11.4% |
| Sweden · Division 2 — dc:x2 | 75 | 49.3% | 57.3% | -8.0% | -24.0% ± 9.3% |
| China · China League 2 — dc:12 | 33 | 57.6% | 70.5% | -12.9% | -25.6% ± 11.3% |
| Portugal · Campeonato de Portugal — btts:no | 47 | 42.6% | 51.5% | -8.9% | -25.9% ± 12.7% |
| Sweden · Division 2 — btts:no | 68 | 30.9% | 36.8% | -5.9% | -27.0% ± 13.5% |
| Turkiye · 1. Lig — dc:1x | 40 | 55.0% | 67.6% | -12.6% | -27.4% ± 10.7% |
| England · National League — dc:1x | 35 | 57.1% | 68.9% | -11.7% | -28.9% ± 10.7% |
| Saudi Arabia · Saudi Pro League — o/u3.5:under | 33 | 45.5% | 60.5% | -15.0% | -29.2% ± 14.1% |
| England Amateur · Southern League Premier Central — btts:no | 47 | 34.0% | 43.5% | -9.4% | -29.9% ± 14.5% |
| USA · MLS — 1x2:home | 63 | 34.9% | 46.0% | -11.1% | -30.6% ± 12.7% |
| Turkiye · 1. Lig — 1x2:home | 40 | 35.0% | 41.7% | -6.7% | -31.7% ± 15.5% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 2553 | -0.0% | -6.7% |
| not covered | 1x2 | 18999 | +0.0% | -11.1% |
| covered | btts | 1698 | +0.0% | -5.4% |
| not covered | btts | 10598 | +0.0% | -8.9% |
| covered | dc | 2553 | +0.0% | -7.3% |
| not covered | dc | 18024 | -0.0% | -9.4% |
| covered | o/u1.5 | 1688 | +0.0% | -8.1% |
| not covered | o/u1.5 | 9276 | +0.0% | -10.0% |
| covered | o/u2.5 | 1702 | +0.0% | -5.6% |
| not covered | o/u2.5 | 11836 | +0.0% | -7.8% |
| covered | o/u3.5 | 1702 | +0.0% | -5.7% |
| not covered | o/u3.5 | 10706 | +0.0% | -7.2% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 15054 | 48.7% | 48.3% | +0.4% | +0.8% ± 1.0% |
| steady | 43644 | 54.6% | 54.2% | +0.4% | -8.0% ± 0.5% |
| drifted 3%+ | 19737 | 39.0% | 40.2% | -1.2% | -19.6% ± 0.8% |

## Basketball — 1496 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 1489 | 50.4% | 50.1% | +0.4% | -6.4% ± 2.4% |
| hcp:home | 1489 | 49.6% | 49.9% | -0.4% | -7.7% ± 2.4% |
| total:over | 1489 | 51.0% | 50.1% | +1.0% | -5.3% ± 2.4% |
| total:under | 1489 | 49.0% | 49.9% | -1.0% | -9.0% ± 2.4% |
| win:away | 1488 | 42.5% | 43.4% | -0.8% | -11.2% ± 3.4% |
| win:home | 1488 | 57.5% | 56.6% | +0.8% | -6.3% ± 2.6% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 2966 | 50.1% | 50.0% | +0.1% | -6.9% ± 1.7% |
| total @ 1.60–2.00 | 2977 | 50.0% | 50.0% | +0.0% | -7.1% ± 1.7% |
| win @ 1.00–1.30 | 594 | 82.8% | 82.5% | +0.4% | -6.6% ± 1.8% |
| win @ 1.30–1.60 | 506 | 65.2% | 66.0% | -0.8% | -7.8% ± 3.0% |
| win @ 1.60–2.00 | 501 | 50.5% | 53.2% | -2.7% | -10.7% ± 4.0% |
| win @ 2.00–3.00 | 627 | 43.2% | 39.6% | +3.7% | +2.4% ± 4.7% |
| win @ 3.00–5.00 | 424 | 27.1% | 25.6% | +1.5% | -0.2% ± 8.1% |
| win @ 5.00–1000.00 | 324 | 8.3% | 12.6% | -4.3% | -43.5% ± 10.8% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — total:over | 68 | 39.7% | 50.1% | -10.4% | -27.5% ± 10.9% |
| Japan · B League One — win:away | 68 | 35.3% | 45.7% | -10.4% | -33.0% ± 12.8% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 190 | +0.0% | -5.0% |
| not covered | hcp | 2788 | +0.0% | -7.2% |
| covered | total | 190 | +0.0% | -5.1% |
| not covered | total | 2788 | +0.0% | -7.3% |
| covered | win | 190 | +0.0% | -6.0% |
| not covered | win | 2786 | +0.0% | -8.9% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 1353 | 50.1% | 50.3% | -0.2% | +2.3% ± 3.3% |
| steady | 5465 | 51.8% | 51.7% | +0.2% | -6.7% ± 1.3% |
| drifted 3%+ | 1486 | 43.1% | 43.5% | -0.4% | -18.4% ± 2.7% |

