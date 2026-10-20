# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

5008 games graded (81% of 6208 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-20.

## Football — 4241 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 4198 | 31.2% | 32.2% | -1.0% | -14.4% ± 2.4% |
| 1x2:draw | 4198 | 23.3% | 24.7% | -1.5% | -14.7% ± 2.5% |
| 1x2:home | 4198 | 45.6% | 43.1% | +2.5% | -3.3% ± 2.0% |
| btts:no | 3585 | 45.0% | 45.9% | -0.9% | -9.7% ± 1.7% |
| btts:yes | 3585 | 55.0% | 54.1% | +0.9% | -6.4% ± 1.4% |
| dc:12 | 4014 | 76.7% | 74.4% | +2.2% | -4.9% ± 0.8% |
| dc:1x | 4014 | 68.7% | 67.6% | +1.1% | -7.6% ± 1.1% |
| dc:x2 | 4014 | 54.6% | 57.9% | -3.3% | -15.2% ± 1.3% |
| o/u1.5:over | 3174 | 75.9% | 74.3% | +1.6% | -4.6% ± 1.0% |
| o/u1.5:under | 3174 | 24.1% | 25.7% | -1.6% | -12.3% ± 2.9% |
| o/u2.5:over | 3947 | 55.8% | 53.8% | +2.0% | -3.5% ± 1.4% |
| o/u2.5:under | 3947 | 44.2% | 46.2% | -2.0% | -11.6% ± 1.7% |
| o/u3.5:over | 3616 | 36.7% | 36.0% | +0.7% | -5.5% ± 2.2% |
| o/u3.5:under | 3616 | 63.3% | 64.0% | -0.7% | -7.9% ± 1.2% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 327 | 83.5% | 78.1% | +5.4% | -1.1% ± 2.5% |
| 1x2 @ 1.30–1.60 | 773 | 67.0% | 63.6% | +3.4% | -2.8% ± 2.5% |
| 1x2 @ 1.60–2.00 | 1279 | 55.6% | 51.6% | +4.0% | -0.7% ± 2.5% |
| 1x2 @ 2.00–3.00 | 3086 | 39.0% | 37.7% | +1.3% | -5.3% ± 2.2% |
| 1x2 @ 3.00–5.00 | 5565 | 23.5% | 25.4% | -2.0% | -15.7% ± 2.1% |
| 1x2 @ 5.00–1000.00 | 1564 | 12.0% | 13.6% | -1.6% | -18.3% ± 6.1% |
| btts @ 1.00–1.30 | 71 | 69.0% | 73.1% | -4.1% | -14.3% ± 6.9% |
| btts @ 1.30–1.60 | 1470 | 59.6% | 61.6% | -2.0% | -11.5% ± 1.9% |
| btts @ 1.60–2.00 | 3339 | 51.5% | 51.3% | +0.2% | -8.5% ± 1.5% |
| btts @ 2.00–3.00 | 2183 | 41.5% | 40.6% | +0.9% | -5.9% ± 2.4% |
| btts @ 3.00–5.00 | 107 | 33.6% | 27.9% | +5.7% | +10.9% ± 15.2% |
| dc @ 1.00–1.30 | 5526 | 80.5% | 77.3% | +3.2% | -3.8% ± 0.6% |
| dc @ 1.30–1.60 | 3809 | 66.3% | 66.1% | +0.2% | -7.3% ± 1.1% |
| dc @ 1.60–2.00 | 1501 | 46.3% | 52.8% | -6.5% | -19.0% ± 2.3% |
| dc @ 2.00–3.00 | 930 | 34.1% | 40.0% | -6.0% | -21.3% ± 3.6% |
| dc @ 3.00–5.00 | 253 | 14.2% | 26.4% | -12.2% | -49.9% ± 7.8% |
| o/u1.5 @ 1.00–1.30 | 2079 | 80.0% | 78.4% | +1.6% | -4.5% ± 1.1% |
| o/u1.5 @ 1.30–1.60 | 1031 | 68.4% | 67.2% | +1.1% | -5.4% ± 2.0% |
| o/u1.5 @ 1.60–2.00 | 79 | 63.3% | 53.9% | +9.4% | +9.1% ± 9.5% |
| o/u1.5 @ 2.00–3.00 | 651 | 34.1% | 35.8% | -1.7% | -11.1% ± 4.9% |
| o/u1.5 @ 3.00–5.00 | 1970 | 23.0% | 24.9% | -1.9% | -13.6% ± 3.6% |
| o/u1.5 @ 5.00–1000.00 | 538 | 15.1% | 15.8% | -0.7% | -10.4% ± 9.4% |
| o/u2.5 @ 1.00–1.30 | 151 | 78.1% | 75.2% | +2.9% | -3.1% ± 4.2% |
| o/u2.5 @ 1.30–1.60 | 1612 | 64.3% | 63.2% | +1.2% | -5.3% ± 1.8% |
| o/u2.5 @ 1.60–2.00 | 3139 | 53.0% | 52.2% | +0.8% | -5.7% ± 1.6% |
| o/u2.5 @ 2.00–3.00 | 2656 | 39.5% | 40.7% | -1.3% | -9.8% ± 2.2% |
| o/u2.5 @ 3.00–5.00 | 322 | 24.2% | 28.1% | -3.8% | -17.3% ± 8.3% |
| o/u3.5 @ 1.00–1.30 | 885 | 75.0% | 75.8% | -0.7% | -8.2% ± 1.8% |
| o/u3.5 @ 1.30–1.60 | 1846 | 63.9% | 65.1% | -1.2% | -8.5% ± 1.6% |
| o/u3.5 @ 1.60–2.00 | 1203 | 55.2% | 52.9% | +2.3% | -2.8% ± 2.5% |
| o/u3.5 @ 2.00–3.00 | 1973 | 38.7% | 38.7% | +0.0% | -6.1% ± 2.7% |
| o/u3.5 @ 3.00–5.00 | 1264 | 26.8% | 26.5% | +0.3% | -5.5% ± 4.4% |
| o/u3.5 @ 5.00–1000.00 | 61 | 8.2% | 16.4% | -8.2% | -54.6% ± 19.6% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| USA · MLS — 1x2:draw | 38 | 42.1% | 23.1% | +19.0% | +72.4% ± 33.8% |
| Spain · Primera Federacion — dc:1x | 31 | 87.1% | 68.6% | +18.5% | +17.7% ± 8.6% |
| Sweden · Division 2 — dc:12 | 73 | 90.4% | 76.2% | +14.2% | +8.8% ± 4.2% |
| Spain · Segunda Federacion — dc:12 | 65 | 58.5% | 71.4% | -12.9% | -25.6% ± 7.8% |
| Sweden · Division 2 — dc:x2 | 73 | 47.9% | 57.2% | -9.3% | -26.0% ± 9.5% |
| USA · MLS — dc:12 | 38 | 57.9% | 75.8% | -17.9% | -28.1% ± 10.1% |
| England · Championship — dc:1x | 32 | 53.1% | 69.8% | -16.7% | -30.8% ± 11.8% |
| USA · MLS — 1x2:home | 38 | 34.2% | 45.5% | -11.3% | -33.7% ± 15.7% |
| Sweden · Division 2 — o/u3.5:under | 66 | 37.9% | 53.2% | -15.3% | -35.9% ± 10.3% |
| Sweden · Division 2 — o/u2.5:under | 65 | 23.1% | 34.4% | -11.3% | -37.2% ± 14.5% |
| Spain · Segunda Federacion — 1x2:away | 65 | 20.0% | 28.8% | -8.8% | -38.0% ± 16.1% |
| Hungary · NB III — 1x2:away | 39 | 25.6% | 30.0% | -4.4% | -38.7% ± 19.1% |
| USA · MLS — 1x2:away | 38 | 23.7% | 31.4% | -7.7% | -40.3% ± 18.6% |
| Spain · Primera Federacion — 1x2:away | 31 | 12.9% | 31.2% | -18.3% | -60.6% ± 19.2% |
| Sweden · Division 2 — 1x2:draw | 73 | 9.6% | 22.5% | -12.9% | -64.0% ± 13.0% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 1395 | -0.0% | -7.1% |
| not covered | 1x2 | 11199 | -0.0% | -11.2% |
| covered | btts | 928 | +0.0% | -4.2% |
| not covered | btts | 6242 | +0.0% | -8.7% |
| covered | dc | 1395 | +0.0% | -7.3% |
| not covered | dc | 10647 | -0.0% | -9.5% |
| covered | o/u1.5 | 922 | +0.0% | -5.7% |
| not covered | o/u1.5 | 5426 | +0.0% | -8.9% |
| covered | o/u2.5 | 930 | +0.0% | -5.4% |
| not covered | o/u2.5 | 6964 | +0.0% | -7.8% |
| covered | o/u3.5 | 930 | +0.0% | -5.7% |
| not covered | o/u3.5 | 6302 | +0.0% | -6.9% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 8578 | 48.3% | 48.1% | +0.2% | +0.2% ± 1.4% |
| steady | 26920 | 54.5% | 54.1% | +0.4% | -8.0% ± 0.6% |
| drifted 3%+ | 11291 | 38.9% | 40.1% | -1.2% | -19.3% ± 1.1% |

## Basketball — 767 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 764 | 50.4% | 50.1% | +0.3% | -6.7% ± 3.4% |
| hcp:home | 764 | 49.6% | 49.9% | -0.3% | -7.8% ± 3.4% |
| total:over | 763 | 53.3% | 50.1% | +3.3% | -1.2% ± 3.4% |
| total:under | 763 | 46.7% | 49.9% | -3.3% | -13.4% ± 3.4% |
| win:away | 762 | 43.2% | 43.3% | -0.1% | -10.3% ± 4.6% |
| win:home | 762 | 56.8% | 56.7% | +0.1% | -8.7% ± 3.5% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 1522 | 50.1% | 50.0% | +0.1% | -7.1% ± 2.4% |
| total @ 1.60–2.00 | 1525 | 50.0% | 50.0% | +0.0% | -7.2% ± 2.4% |
| win @ 1.00–1.30 | 295 | 83.4% | 82.3% | +1.1% | -5.9% ± 2.5% |
| win @ 1.30–1.60 | 279 | 65.6% | 65.9% | -0.3% | -7.0% ± 4.1% |
| win @ 1.60–2.00 | 247 | 49.4% | 53.0% | -3.6% | -12.3% ± 5.7% |
| win @ 2.00–3.00 | 329 | 42.2% | 39.1% | +3.1% | +0.6% ± 6.6% |
| win @ 3.00–5.00 | 211 | 28.9% | 26.1% | +2.9% | +4.7% ± 11.5% |
| win @ 5.00–1000.00 | 163 | 6.7% | 12.7% | -6.0% | -54.8% ± 13.5% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — win:away | 41 | 34.1% | 44.7% | -10.6% | -41.2% ± 13.6% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 78 | +0.0% | -6.6% |
| not covered | hcp | 1450 | +0.0% | -7.2% |
| covered | total | 78 | +0.0% | -6.8% |
| not covered | total | 1448 | +0.0% | -7.3% |
| covered | win | 78 | +0.0% | -2.9% |
| not covered | win | 1446 | +0.0% | -9.9% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 686 | 49.7% | 50.2% | -0.5% | +1.0% ± 4.6% |
| steady | 2790 | 51.8% | 51.7% | +0.1% | -6.8% ± 1.8% |
| drifted 3%+ | 746 | 43.7% | 43.5% | +0.2% | -18.3% ± 3.7% |

