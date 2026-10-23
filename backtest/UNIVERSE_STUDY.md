# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

5549 games graded (78% of 7140 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-23.

## Football — 4611 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 4554 | 31.0% | 32.3% | -1.2% | -15.2% ± 2.3% |
| 1x2:draw | 4554 | 23.4% | 24.6% | -1.3% | -13.9% ± 2.4% |
| 1x2:home | 4554 | 45.6% | 43.1% | +2.5% | -3.2% ± 2.0% |
| btts:no | 3913 | 44.7% | 45.9% | -1.1% | -10.1% ± 1.6% |
| btts:yes | 3913 | 55.3% | 54.1% | +1.1% | -6.0% ± 1.4% |
| dc:12 | 4356 | 76.5% | 74.5% | +2.0% | -5.1% ± 0.8% |
| dc:1x | 4356 | 68.9% | 67.6% | +1.3% | -7.3% ± 1.0% |
| dc:x2 | 4356 | 54.6% | 57.9% | -3.3% | -15.1% ± 1.3% |
| o/u1.5:over | 3464 | 76.4% | 74.4% | +1.9% | -4.1% ± 0.9% |
| o/u1.5:under | 3464 | 23.6% | 25.6% | -1.9% | -13.6% ± 2.8% |
| o/u2.5:over | 4294 | 56.3% | 54.0% | +2.4% | -2.9% ± 1.4% |
| o/u2.5:under | 4294 | 43.7% | 46.0% | -2.4% | -12.1% ± 1.6% |
| o/u3.5:over | 3938 | 37.1% | 36.1% | +1.0% | -4.7% ± 2.1% |
| o/u3.5:under | 3938 | 62.9% | 63.9% | -1.0% | -8.4% ± 1.2% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 369 | 83.2% | 78.1% | +5.1% | -1.3% ± 2.3% |
| 1x2 @ 1.30–1.60 | 848 | 67.1% | 63.7% | +3.4% | -2.7% ± 2.4% |
| 1x2 @ 1.60–2.00 | 1377 | 55.6% | 51.6% | +4.0% | -0.6% ± 2.4% |
| 1x2 @ 2.00–3.00 | 3318 | 38.9% | 37.7% | +1.2% | -5.4% ± 2.1% |
| 1x2 @ 3.00–5.00 | 6006 | 23.5% | 25.4% | -1.9% | -15.2% ± 2.0% |
| 1x2 @ 5.00–1000.00 | 1744 | 11.9% | 13.6% | -1.7% | -19.6% ± 5.7% |
| btts @ 1.00–1.30 | 76 | 71.1% | 73.2% | -2.2% | -11.7% ± 6.5% |
| btts @ 1.30–1.60 | 1602 | 59.7% | 61.5% | -1.9% | -11.3% ± 1.8% |
| btts @ 1.60–2.00 | 3631 | 51.4% | 51.3% | +0.0% | -8.6% ± 1.5% |
| btts @ 2.00–3.00 | 2404 | 41.6% | 40.6% | +1.0% | -5.7% ± 2.3% |
| btts @ 3.00–5.00 | 113 | 32.7% | 27.9% | +4.9% | +7.7% ± 14.7% |
| dc @ 1.00–1.30 | 6003 | 80.7% | 77.4% | +3.3% | -3.7% ± 0.6% |
| dc @ 1.30–1.60 | 4113 | 66.1% | 66.2% | -0.0% | -7.6% ± 1.0% |
| dc @ 1.60–2.00 | 1619 | 46.6% | 52.8% | -6.2% | -18.6% ± 2.2% |
| dc @ 2.00–3.00 | 1022 | 34.2% | 40.0% | -5.8% | -20.8% ± 3.5% |
| dc @ 3.00–5.00 | 286 | 14.7% | 26.5% | -11.8% | -48.2% ± 7.5% |
| o/u1.5 @ 1.00–1.30 | 2299 | 80.4% | 78.4% | +2.0% | -3.9% ± 1.0% |
| o/u1.5 @ 1.30–1.60 | 1093 | 68.6% | 67.3% | +1.3% | -5.1% ± 1.9% |
| o/u1.5 @ 1.60–2.00 | 91 | 63.7% | 53.7% | +10.0% | +10.0% ± 8.8% |
| o/u1.5 @ 2.00–3.00 | 681 | 34.4% | 35.8% | -1.4% | -10.5% ± 4.8% |
| o/u1.5 @ 3.00–5.00 | 2157 | 22.3% | 24.9% | -2.5% | -15.9% ± 3.4% |
| o/u1.5 @ 5.00–1000.00 | 607 | 15.0% | 15.8% | -0.8% | -10.3% ± 8.8% |
| o/u2.5 @ 1.00–1.30 | 172 | 78.5% | 75.3% | +3.1% | -2.7% ± 3.9% |
| o/u2.5 @ 1.30–1.60 | 1748 | 64.3% | 63.3% | +1.0% | -5.4% ± 1.7% |
| o/u2.5 @ 1.60–2.00 | 3408 | 53.2% | 52.3% | +0.9% | -5.5% ± 1.5% |
| o/u2.5 @ 2.00–3.00 | 2878 | 39.2% | 40.7% | -1.5% | -10.2% ± 2.1% |
| o/u2.5 @ 3.00–5.00 | 366 | 24.9% | 28.0% | -3.1% | -15.4% ± 7.8% |
| o/u3.5 @ 1.00–1.30 | 936 | 75.0% | 75.8% | -0.8% | -8.2% ± 1.7% |
| o/u3.5 @ 1.30–1.60 | 2024 | 63.8% | 65.1% | -1.3% | -8.6% ± 1.5% |
| o/u3.5 @ 1.60–2.00 | 1317 | 54.8% | 53.0% | +1.9% | -3.5% ± 2.4% |
| o/u3.5 @ 2.00–3.00 | 2181 | 38.9% | 38.7% | +0.2% | -5.6% ± 2.6% |
| o/u3.5 @ 3.00–5.00 | 1353 | 27.1% | 26.6% | +0.6% | -4.8% ± 4.3% |
| o/u3.5 @ 5.00–1000.00 | 65 | 9.2% | 16.4% | -7.2% | -48.5% ± 20.2% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| USA · MLS — 1x2:draw | 39 | 41.0% | 23.1% | +18.0% | +68.0% ± 33.2% |
| Spain · Primera Federacion — dc:1x | 31 | 87.1% | 68.6% | +18.5% | +17.7% ± 8.6% |
| Sweden · Division 2 — dc:12 | 73 | 90.4% | 76.2% | +14.2% | +8.8% ± 4.2% |
| Spain · Segunda Federacion — dc:12 | 66 | 59.1% | 71.4% | -12.4% | -24.9% ± 7.8% |
| Sweden · Division 2 — dc:x2 | 73 | 47.9% | 57.2% | -9.3% | -26.0% ± 9.5% |
| USA · MLS — dc:12 | 39 | 59.0% | 75.9% | -16.9% | -26.8% ± 9.9% |
| England · Championship — dc:1x | 33 | 54.5% | 70.1% | -15.6% | -29.4% ± 11.6% |
| USA · MLS — 1x2:home | 39 | 35.9% | 45.8% | -9.9% | -31.2% ± 15.5% |
| England · League One — dc:x2 | 33 | 42.4% | 54.6% | -12.2% | -31.9% ± 14.6% |
| International Clubs · UEFA Champions League — o/u3.5:under | 36 | 36.1% | 52.3% | -16.2% | -34.2% ± 14.9% |
| Sweden · Division 2 — o/u3.5:under | 66 | 37.9% | 53.2% | -15.3% | -35.9% ± 10.3% |
| Sweden · Division 2 — o/u2.5:under | 65 | 23.1% | 34.4% | -11.3% | -37.2% ± 14.5% |
| Hungary · NB III — 1x2:away | 39 | 25.6% | 30.0% | -4.4% | -38.7% ± 19.1% |
| Spain · Segunda Federacion — 1x2:away | 66 | 19.7% | 28.7% | -9.0% | -38.9% ± 15.9% |
| International Youth · UEFA Youth League — dc:x2 | 31 | 35.5% | 52.0% | -16.5% | -40.8% ± 16.0% |
| USA · MLS — 1x2:away | 39 | 23.1% | 31.1% | -8.0% | -41.8% ± 18.2% |
| England Amateur · Southern League Premier Central — 1x2:away | 34 | 23.5% | 31.5% | -8.0% | -44.8% ± 18.0% |
| International Clubs · UEFA Europa League — o/u2.5:under | 31 | 22.6% | 39.1% | -16.6% | -45.5% ± 18.8% |
| International Clubs · UEFA Europa League — o/u1.5:under | 31 | 9.7% | 18.7% | -9.0% | -55.8% ± 24.8% |
| Spain · Primera Federacion — 1x2:away | 31 | 12.9% | 31.2% | -18.3% | -60.6% ± 19.2% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 1653 | -0.0% | -6.8% |
| not covered | 1x2 | 12009 | -0.0% | -11.3% |
| covered | btts | 1100 | +0.0% | -4.3% |
| not covered | btts | 6726 | +0.0% | -8.7% |
| covered | dc | 1653 | +0.0% | -7.2% |
| not covered | dc | 11415 | +0.0% | -9.5% |
| covered | o/u1.5 | 1094 | +0.0% | -6.6% |
| not covered | o/u1.5 | 5834 | +0.0% | -9.3% |
| covered | o/u2.5 | 1102 | +0.0% | -5.7% |
| not covered | o/u2.5 | 7486 | +0.0% | -7.7% |
| covered | o/u3.5 | 1102 | +0.0% | -5.0% |
| not covered | o/u3.5 | 6774 | +0.0% | -6.8% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 9545 | 48.5% | 48.3% | +0.1% | +0.1% ± 1.3% |
| steady | 28806 | 54.6% | 54.2% | +0.4% | -7.9% ± 0.6% |
| drifted 3%+ | 12517 | 39.0% | 40.1% | -1.1% | -19.3% ± 1.1% |

## Basketball — 938 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 934 | 50.1% | 50.1% | +0.0% | -7.1% ± 3.0% |
| hcp:home | 934 | 49.9% | 49.9% | -0.0% | -7.1% ± 3.0% |
| total:over | 933 | 52.6% | 50.1% | +2.5% | -2.5% ± 3.0% |
| total:under | 933 | 47.4% | 49.9% | -2.5% | -12.0% ± 3.0% |
| win:away | 931 | 42.3% | 42.6% | -0.3% | -10.3% ± 4.3% |
| win:home | 931 | 57.7% | 57.4% | +0.3% | -7.5% ± 3.2% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 1861 | 50.0% | 50.0% | +0.0% | -7.1% ± 2.2% |
| total @ 1.60–2.00 | 1865 | 50.0% | 50.0% | +0.0% | -7.2% ± 2.2% |
| win @ 1.00–1.30 | 365 | 82.5% | 82.4% | +0.0% | -7.2% ± 2.3% |
| win @ 1.30–1.60 | 333 | 65.8% | 66.0% | -0.2% | -6.8% ± 3.7% |
| win @ 1.60–2.00 | 302 | 50.3% | 53.1% | -2.7% | -10.8% ± 5.1% |
| win @ 2.00–3.00 | 400 | 42.2% | 39.4% | +2.9% | +0.4% ± 6.0% |
| win @ 3.00–5.00 | 259 | 29.3% | 25.9% | +3.5% | +8.1% ± 10.6% |
| win @ 5.00–1000.00 | 203 | 6.9% | 12.7% | -5.8% | -52.6% ± 12.8% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — win:away | 42 | 33.3% | 45.3% | -11.9% | -42.6% ± 13.3% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 106 | +0.0% | -5.8% |
| not covered | hcp | 1762 | +0.0% | -7.2% |
| covered | total | 106 | +0.0% | -5.9% |
| not covered | total | 1760 | +0.0% | -7.3% |
| covered | win | 106 | +0.0% | -5.4% |
| not covered | win | 1756 | +0.0% | -9.1% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 829 | 50.2% | 50.4% | -0.2% | +3.0% ± 4.3% |
| steady | 3417 | 51.9% | 51.7% | +0.1% | -6.7% ± 1.6% |
| drifted 3%+ | 918 | 42.9% | 43.2% | -0.3% | -19.3% ± 3.4% |

