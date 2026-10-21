# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

5199 games graded (80% of 6526 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-21.

## Football — 4384 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 4337 | 31.2% | 32.2% | -1.0% | -14.6% ± 2.3% |
| 1x2:draw | 4337 | 23.3% | 24.7% | -1.4% | -14.6% ± 2.4% |
| 1x2:home | 4337 | 45.5% | 43.1% | +2.4% | -3.6% ± 2.0% |
| btts:no | 3715 | 44.9% | 45.9% | -1.0% | -9.8% ± 1.7% |
| btts:yes | 3715 | 55.1% | 54.1% | +1.0% | -6.3% ± 1.4% |
| dc:12 | 4146 | 76.6% | 74.5% | +2.2% | -5.0% ± 0.8% |
| dc:1x | 4146 | 68.7% | 67.6% | +1.1% | -7.7% ± 1.0% |
| dc:x2 | 4146 | 54.7% | 57.9% | -3.2% | -15.1% ± 1.3% |
| o/u1.5:over | 3286 | 76.1% | 74.4% | +1.7% | -4.4% ± 1.0% |
| o/u1.5:under | 3286 | 23.9% | 25.6% | -1.7% | -12.9% ± 2.9% |
| o/u2.5:over | 4080 | 55.9% | 53.9% | +2.1% | -3.4% ± 1.4% |
| o/u2.5:under | 4080 | 44.1% | 46.1% | -2.1% | -11.5% ± 1.6% |
| o/u3.5:over | 3746 | 36.9% | 36.1% | +0.8% | -5.3% ± 2.1% |
| o/u3.5:under | 3746 | 63.1% | 63.9% | -0.8% | -8.1% ± 1.2% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 342 | 83.9% | 78.2% | +5.7% | -0.7% ± 2.4% |
| 1x2 @ 1.30–1.60 | 805 | 66.7% | 63.6% | +3.1% | -3.2% ± 2.4% |
| 1x2 @ 1.60–2.00 | 1315 | 55.9% | 51.6% | +4.3% | -0.2% ± 2.5% |
| 1x2 @ 2.00–3.00 | 3182 | 38.9% | 37.7% | +1.2% | -5.4% ± 2.1% |
| 1x2 @ 3.00–5.00 | 5735 | 23.5% | 25.4% | -1.9% | -15.6% ± 2.0% |
| 1x2 @ 5.00–1000.00 | 1632 | 11.8% | 13.6% | -1.8% | -19.9% ± 5.9% |
| btts @ 1.00–1.30 | 73 | 69.9% | 73.2% | -3.3% | -13.2% ± 6.7% |
| btts @ 1.30–1.60 | 1522 | 59.5% | 61.5% | -2.1% | -11.7% ± 1.9% |
| btts @ 1.60–2.00 | 3443 | 51.4% | 51.3% | +0.0% | -8.6% ± 1.5% |
| btts @ 2.00–3.00 | 2282 | 41.8% | 40.6% | +1.2% | -5.5% ± 2.4% |
| btts @ 3.00–5.00 | 110 | 33.6% | 27.9% | +5.7% | +10.6% ± 15.0% |
| dc @ 1.00–1.30 | 5707 | 80.6% | 77.4% | +3.3% | -3.7% ± 0.6% |
| dc @ 1.30–1.60 | 3935 | 66.3% | 66.1% | +0.1% | -7.4% ± 1.1% |
| dc @ 1.60–2.00 | 1544 | 46.2% | 52.8% | -6.6% | -19.3% ± 2.2% |
| dc @ 2.00–3.00 | 964 | 34.4% | 40.1% | -5.6% | -20.5% ± 3.6% |
| dc @ 3.00–5.00 | 263 | 13.7% | 26.4% | -12.7% | -51.8% ± 7.6% |
| o/u1.5 @ 1.00–1.30 | 2166 | 80.1% | 78.4% | +1.7% | -4.3% ± 1.0% |
| o/u1.5 @ 1.30–1.60 | 1052 | 68.5% | 67.2% | +1.3% | -5.2% ± 2.0% |
| o/u1.5 @ 1.60–2.00 | 86 | 62.8% | 53.7% | +9.1% | +8.3% ± 9.1% |
| o/u1.5 @ 2.00–3.00 | 659 | 34.1% | 35.8% | -1.6% | -11.0% ± 4.9% |
| o/u1.5 @ 3.00–5.00 | 2050 | 22.8% | 24.9% | -2.1% | -14.2% ± 3.5% |
| o/u1.5 @ 5.00–1000.00 | 559 | 14.8% | 15.8% | -0.9% | -11.6% ± 9.1% |
| o/u2.5 @ 1.00–1.30 | 162 | 77.8% | 75.2% | +2.5% | -3.4% ± 4.1% |
| o/u2.5 @ 1.30–1.60 | 1662 | 64.3% | 63.2% | +1.1% | -5.4% ± 1.7% |
| o/u2.5 @ 1.60–2.00 | 3242 | 53.1% | 52.2% | +0.9% | -5.6% ± 1.6% |
| o/u2.5 @ 2.00–3.00 | 2741 | 39.4% | 40.7% | -1.3% | -9.8% ± 2.2% |
| o/u2.5 @ 3.00–5.00 | 338 | 24.3% | 28.0% | -3.7% | -17.1% ± 8.1% |
| o/u3.5 @ 1.00–1.30 | 901 | 75.0% | 75.8% | -0.8% | -8.2% ± 1.8% |
| o/u3.5 @ 1.30–1.60 | 1925 | 63.9% | 65.1% | -1.2% | -8.6% ± 1.6% |
| o/u3.5 @ 1.60–2.00 | 1246 | 55.2% | 52.9% | +2.3% | -2.8% ± 2.5% |
| o/u3.5 @ 2.00–3.00 | 2059 | 38.8% | 38.7% | +0.1% | -6.0% ± 2.6% |
| o/u3.5 @ 3.00–5.00 | 1297 | 26.8% | 26.5% | +0.3% | -5.6% ± 4.4% |
| o/u3.5 @ 5.00–1000.00 | 64 | 9.4% | 16.4% | -7.1% | -47.7% ± 20.5% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| USA · MLS — 1x2:draw | 38 | 42.1% | 23.1% | +19.0% | +72.4% ± 33.8% |
| Spain · Primera Federacion — dc:1x | 31 | 87.1% | 68.6% | +18.5% | +17.7% ± 8.6% |
| Sweden · Division 2 — dc:12 | 73 | 90.4% | 76.2% | +14.2% | +8.8% ± 4.2% |
| Spain · Segunda Federacion — dc:12 | 65 | 58.5% | 71.4% | -12.9% | -25.6% ± 7.8% |
| Sweden · Division 2 — dc:x2 | 73 | 47.9% | 57.2% | -9.3% | -26.0% ± 9.5% |
| USA · MLS — dc:12 | 38 | 57.9% | 75.8% | -17.9% | -28.1% ± 10.1% |
| England · Championship — dc:1x | 33 | 54.5% | 70.1% | -15.6% | -29.4% ± 11.6% |
| USA · MLS — 1x2:home | 38 | 34.2% | 45.5% | -11.3% | -33.7% ± 15.7% |
| Sweden · Division 2 — o/u3.5:under | 66 | 37.9% | 53.2% | -15.3% | -35.9% ± 10.3% |
| Sweden · Division 2 — o/u2.5:under | 65 | 23.1% | 34.4% | -11.3% | -37.2% ± 14.5% |
| Spain · Segunda Federacion — 1x2:away | 65 | 20.0% | 28.8% | -8.8% | -38.0% ± 16.1% |
| Hungary · NB III — 1x2:away | 39 | 25.6% | 30.0% | -4.4% | -38.7% ± 19.1% |
| USA · MLS — 1x2:away | 38 | 23.7% | 31.4% | -7.7% | -40.3% ± 18.6% |
| England Amateur · Southern League Premier Central — 1x2:away | 34 | 23.5% | 31.5% | -8.0% | -44.8% ± 18.0% |
| Spain · Primera Federacion — 1x2:away | 31 | 12.9% | 31.2% | -18.3% | -60.6% ± 19.2% |
| Sweden · Division 2 — 1x2:draw | 73 | 9.6% | 22.5% | -12.9% | -64.0% ± 13.0% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 1521 | +0.0% | -7.4% |
| not covered | 1x2 | 11490 | -0.0% | -11.4% |
| covered | btts | 1012 | +0.0% | -4.5% |
| not covered | btts | 6418 | +0.0% | -8.6% |
| covered | dc | 1521 | +0.0% | -7.4% |
| not covered | dc | 10917 | -0.0% | -9.5% |
| covered | o/u1.5 | 1006 | +0.0% | -7.5% |
| not covered | o/u1.5 | 5566 | +0.0% | -8.9% |
| covered | o/u2.5 | 1014 | +0.0% | -5.8% |
| not covered | o/u2.5 | 7146 | +0.0% | -7.7% |
| covered | o/u3.5 | 1014 | +0.0% | -5.5% |
| not covered | o/u3.5 | 6478 | +0.0% | -6.9% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 8914 | 48.2% | 48.1% | +0.1% | -0.1% ± 1.3% |
| steady | 27593 | 54.6% | 54.1% | +0.5% | -8.0% ± 0.6% |
| drifted 3%+ | 11705 | 39.0% | 40.1% | -1.2% | -19.3% ± 1.1% |

## Basketball — 815 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 812 | 50.1% | 50.1% | +0.0% | -7.2% ± 3.3% |
| hcp:home | 812 | 49.9% | 49.9% | -0.0% | -7.2% ± 3.3% |
| total:over | 810 | 53.7% | 50.1% | +3.6% | -0.5% ± 3.3% |
| total:under | 810 | 46.3% | 49.9% | -3.6% | -14.1% ± 3.3% |
| win:away | 808 | 43.1% | 43.0% | +0.0% | -9.1% ± 4.7% |
| win:home | 808 | 56.9% | 57.0% | -0.0% | -8.9% ± 3.4% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 1618 | 50.1% | 50.0% | +0.1% | -7.1% ± 2.3% |
| total @ 1.60–2.00 | 1619 | 50.0% | 50.0% | +0.0% | -7.2% ± 2.3% |
| win @ 1.00–1.30 | 317 | 83.3% | 82.3% | +1.0% | -6.0% ± 2.4% |
| win @ 1.30–1.60 | 292 | 65.4% | 65.9% | -0.5% | -7.2% ± 4.0% |
| win @ 1.60–2.00 | 259 | 49.4% | 53.1% | -3.6% | -12.3% ± 5.5% |
| win @ 2.00–3.00 | 349 | 42.4% | 39.2% | +3.2% | +0.9% ± 6.4% |
| win @ 3.00–5.00 | 224 | 29.0% | 26.0% | +3.0% | +5.6% ± 11.2% |
| win @ 5.00–1000.00 | 175 | 6.9% | 12.8% | -5.9% | -51.1% ± 14.2% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — win:away | 41 | 34.1% | 44.7% | -10.6% | -41.2% ± 13.6% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 82 | +0.0% | -6.4% |
| not covered | hcp | 1542 | +0.0% | -7.2% |
| covered | total | 82 | +0.0% | -6.7% |
| not covered | total | 1538 | +0.0% | -7.3% |
| covered | win | 82 | +0.0% | -2.9% |
| not covered | win | 1534 | +0.0% | -9.3% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 732 | 49.9% | 50.4% | -0.5% | +1.9% ± 4.5% |
| steady | 2952 | 51.9% | 51.7% | +0.2% | -6.6% ± 1.8% |
| drifted 3%+ | 790 | 43.2% | 43.3% | -0.1% | -18.8% ± 3.7% |

