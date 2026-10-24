# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

5869 games graded (77% of 7655 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-24.

## Football — 4854 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 4793 | 31.2% | 32.3% | -1.1% | -15.1% ± 2.2% |
| 1x2:draw | 4793 | 23.5% | 24.6% | -1.1% | -13.3% ± 2.3% |
| 1x2:home | 4793 | 45.3% | 43.1% | +2.2% | -3.9% ± 1.9% |
| btts:no | 4127 | 44.4% | 45.9% | -1.5% | -11.0% ± 1.6% |
| btts:yes | 4127 | 55.6% | 54.1% | +1.5% | -5.5% ± 1.4% |
| dc:12 | 4592 | 76.4% | 74.5% | +1.9% | -5.3% ± 0.8% |
| dc:1x | 4592 | 68.7% | 67.6% | +1.1% | -7.6% ± 1.0% |
| dc:x2 | 4592 | 54.9% | 57.9% | -3.0% | -14.7% ± 1.2% |
| o/u1.5:over | 3654 | 76.5% | 74.4% | +2.0% | -4.0% ± 0.9% |
| o/u1.5:under | 3654 | 23.5% | 25.6% | -2.0% | -14.4% ± 2.7% |
| o/u2.5:over | 4518 | 56.4% | 54.0% | +2.4% | -2.8% ± 1.3% |
| o/u2.5:under | 4518 | 43.6% | 46.0% | -2.4% | -12.3% ± 1.6% |
| o/u3.5:over | 4154 | 37.3% | 36.1% | +1.2% | -4.5% ± 2.0% |
| o/u3.5:under | 4154 | 62.7% | 63.9% | -1.2% | -8.8% ± 1.1% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 392 | 82.9% | 78.1% | +4.8% | -1.8% ± 2.3% |
| 1x2 @ 1.30–1.60 | 894 | 67.6% | 63.6% | +3.9% | -2.0% ± 2.3% |
| 1x2 @ 1.60–2.00 | 1438 | 55.4% | 51.6% | +3.8% | -1.0% ± 2.4% |
| 1x2 @ 2.00–3.00 | 3499 | 38.8% | 37.7% | +1.1% | -5.5% ± 2.0% |
| 1x2 @ 3.00–5.00 | 6322 | 23.7% | 25.4% | -1.7% | -14.7% ± 1.9% |
| 1x2 @ 5.00–1000.00 | 1834 | 11.6% | 13.6% | -2.0% | -21.1% ± 5.5% |
| btts @ 1.00–1.30 | 79 | 70.9% | 73.3% | -2.4% | -12.0% ± 6.4% |
| btts @ 1.30–1.60 | 1695 | 60.6% | 61.6% | -1.0% | -10.0% ± 1.8% |
| btts @ 1.60–2.00 | 3827 | 51.3% | 51.3% | -0.0% | -8.7% ± 1.4% |
| btts @ 2.00–3.00 | 2537 | 41.1% | 40.6% | +0.5% | -7.1% ± 2.2% |
| btts @ 3.00–5.00 | 116 | 32.8% | 27.8% | +5.0% | +8.3% ± 14.6% |
| dc @ 1.00–1.30 | 6311 | 80.6% | 77.4% | +3.2% | -3.8% ± 0.6% |
| dc @ 1.30–1.60 | 4353 | 66.2% | 66.2% | +0.0% | -7.5% ± 1.0% |
| dc @ 1.60–2.00 | 1706 | 46.9% | 52.8% | -5.9% | -18.1% ± 2.1% |
| dc @ 2.00–3.00 | 1075 | 34.0% | 40.0% | -6.0% | -21.4% ± 3.4% |
| dc @ 3.00–5.00 | 305 | 14.8% | 26.4% | -11.7% | -47.8% ± 7.3% |
| o/u1.5 @ 1.00–1.30 | 2429 | 80.5% | 78.4% | +2.1% | -3.8% ± 1.0% |
| o/u1.5 @ 1.30–1.60 | 1150 | 68.9% | 67.3% | +1.6% | -4.8% ± 1.9% |
| o/u1.5 @ 1.60–2.00 | 94 | 62.8% | 53.8% | +9.0% | +8.1% ± 8.7% |
| o/u1.5 @ 2.00–3.00 | 715 | 34.8% | 35.8% | -1.0% | -9.5% ± 4.7% |
| o/u1.5 @ 3.00–5.00 | 2286 | 22.2% | 24.9% | -2.7% | -16.4% ± 3.3% |
| o/u1.5 @ 5.00–1000.00 | 634 | 14.4% | 15.8% | -1.5% | -14.1% ± 8.5% |
| o/u2.5 @ 1.00–1.30 | 175 | 78.9% | 75.3% | +3.5% | -2.2% ± 3.9% |
| o/u2.5 @ 1.30–1.60 | 1846 | 64.7% | 63.3% | +1.4% | -4.9% ± 1.6% |
| o/u2.5 @ 1.60–2.00 | 3581 | 53.2% | 52.3% | +0.9% | -5.5% ± 1.5% |
| o/u2.5 @ 2.00–3.00 | 3042 | 39.1% | 40.7% | -1.7% | -10.6% ± 2.0% |
| o/u2.5 @ 3.00–5.00 | 376 | 24.5% | 28.0% | -3.5% | -16.9% ± 7.6% |
| o/u3.5 @ 1.00–1.30 | 978 | 74.9% | 75.8% | -0.8% | -8.2% ± 1.7% |
| o/u3.5 @ 1.30–1.60 | 2147 | 64.2% | 65.1% | -0.9% | -8.1% ± 1.5% |
| o/u3.5 @ 1.60–2.00 | 1388 | 54.3% | 52.9% | +1.4% | -4.2% ± 2.4% |
| o/u3.5 @ 2.00–3.00 | 2305 | 38.8% | 38.7% | +0.2% | -6.0% ± 2.5% |
| o/u3.5 @ 3.00–5.00 | 1424 | 27.2% | 26.6% | +0.6% | -4.7% ± 4.2% |
| o/u3.5 @ 5.00–1000.00 | 66 | 9.1% | 16.4% | -7.3% | -49.3% ± 19.9% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| USA · MLS — 1x2:draw | 39 | 41.0% | 23.1% | +18.0% | +68.0% ± 33.2% |
| Sweden · Division 2 — dc:12 | 73 | 90.4% | 76.2% | +14.2% | +8.8% ± 4.2% |
| Spain · Segunda Federacion — dc:12 | 66 | 59.1% | 71.4% | -12.4% | -24.9% ± 7.8% |
| Sweden · Division 2 — dc:x2 | 73 | 47.9% | 57.2% | -9.3% | -26.0% ± 9.5% |
| USA · MLS — dc:12 | 39 | 59.0% | 75.9% | -16.9% | -26.8% ± 9.9% |
| USA · MLS — 1x2:home | 39 | 35.9% | 45.8% | -9.9% | -31.2% ± 15.5% |
| Turkiye · 1. Lig — dc:1x | 30 | 53.3% | 67.7% | -14.3% | -31.3% ± 12.1% |
| England · Championship — dc:1x | 34 | 52.9% | 69.4% | -16.4% | -31.4% ± 11.4% |
| England · League One — dc:x2 | 33 | 42.4% | 54.6% | -12.2% | -31.9% ± 14.6% |
| International Clubs · UEFA Champions League — o/u3.5:under | 36 | 36.1% | 52.3% | -16.2% | -34.2% ± 14.9% |
| Sweden · Division 2 — o/u3.5:under | 66 | 37.9% | 53.2% | -15.3% | -35.9% ± 10.3% |
| Sweden · Division 2 — o/u2.5:under | 65 | 23.1% | 34.4% | -11.3% | -37.2% ± 14.5% |
| Hungary · NB III — 1x2:away | 39 | 25.6% | 30.0% | -4.4% | -38.7% ± 19.1% |
| Spain · Segunda Federacion — 1x2:away | 66 | 19.7% | 28.7% | -9.0% | -38.9% ± 15.9% |
| International Youth · UEFA Youth League — dc:x2 | 31 | 35.5% | 52.0% | -16.5% | -40.8% ± 16.0% |
| USA · MLS — 1x2:away | 39 | 23.1% | 31.1% | -8.0% | -41.8% ± 18.2% |
| Turkiye · 1. Lig — 1x2:home | 30 | 30.0% | 42.1% | -12.1% | -44.1% ± 16.5% |
| England Amateur · Southern League Premier Central — 1x2:away | 34 | 23.5% | 31.5% | -8.0% | -44.8% ± 18.0% |
| International Clubs · UEFA Europa League — o/u2.5:under | 31 | 22.6% | 39.1% | -16.6% | -45.5% ± 18.8% |
| Algeria · Ligue 2 — 1x2:draw | 30 | 16.7% | 28.1% | -11.5% | -49.6% ± 21.0% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 1716 | -0.0% | -6.8% |
| not covered | 1x2 | 12663 | -0.0% | -11.3% |
| covered | btts | 1142 | +0.0% | -4.6% |
| not covered | btts | 7112 | +0.0% | -8.8% |
| covered | dc | 1716 | +0.0% | -7.2% |
| not covered | dc | 12060 | +0.0% | -9.5% |
| covered | o/u1.5 | 1136 | +0.0% | -7.0% |
| not covered | o/u1.5 | 6172 | +0.0% | -9.6% |
| covered | o/u2.5 | 1144 | +0.0% | -5.5% |
| not covered | o/u2.5 | 7892 | +0.0% | -7.9% |
| covered | o/u3.5 | 1144 | +0.0% | -5.2% |
| not covered | o/u3.5 | 7164 | +0.0% | -6.9% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 10115 | 48.5% | 48.4% | +0.2% | +0.1% ± 1.2% |
| steady | 30080 | 54.7% | 54.3% | +0.4% | -8.0% ± 0.6% |
| drifted 3%+ | 13253 | 39.1% | 40.2% | -1.1% | -19.5% ± 1.0% |

## Basketball — 1015 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 1011 | 50.0% | 50.1% | -0.1% | -7.4% ± 2.9% |
| hcp:home | 1011 | 50.0% | 49.9% | +0.1% | -6.9% ± 2.9% |
| total:over | 1010 | 52.2% | 50.1% | +2.1% | -3.3% ± 2.9% |
| total:under | 1010 | 47.8% | 49.9% | -2.1% | -11.1% ± 2.9% |
| win:away | 1008 | 42.8% | 42.8% | -0.1% | -9.2% ± 4.2% |
| win:home | 1008 | 57.2% | 57.2% | +0.1% | -8.6% ± 3.0% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 2015 | 50.0% | 50.0% | +0.0% | -7.1% ± 2.1% |
| total @ 1.60–2.00 | 2019 | 50.0% | 50.0% | +0.0% | -7.2% ± 2.1% |
| win @ 1.00–1.30 | 398 | 82.4% | 82.4% | -0.0% | -7.1% ± 2.2% |
| win @ 1.30–1.60 | 355 | 66.5% | 65.9% | +0.5% | -5.9% ± 3.6% |
| win @ 1.60–2.00 | 331 | 51.1% | 53.1% | -2.0% | -9.5% ± 4.9% |
| win @ 2.00–3.00 | 431 | 41.5% | 39.4% | +2.1% | -1.5% ± 5.7% |
| win @ 3.00–5.00 | 281 | 28.1% | 25.8% | +2.3% | +4.2% ± 10.1% |
| win @ 5.00–1000.00 | 220 | 7.7% | 12.7% | -4.9% | -47.4% ± 12.7% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — win:away | 53 | 34.0% | 43.8% | -9.9% | -33.7% ± 14.9% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 120 | +0.0% | -5.7% |
| not covered | hcp | 1902 | +0.0% | -7.2% |
| covered | total | 120 | +0.0% | -5.7% |
| not covered | total | 1900 | +0.0% | -7.3% |
| covered | win | 120 | +0.0% | -4.9% |
| not covered | win | 1896 | +0.0% | -9.2% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 898 | 49.8% | 50.3% | -0.5% | +1.9% ± 4.1% |
| steady | 3706 | 51.9% | 51.7% | +0.2% | -6.7% ± 1.6% |
| drifted 3%+ | 994 | 43.1% | 43.3% | -0.2% | -18.6% ± 3.3% |

