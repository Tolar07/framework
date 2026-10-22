# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

5402 games graded (79% of 6878 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-22.

## Football — 4510 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 4459 | 31.0% | 32.2% | -1.2% | -15.0% ± 2.3% |
| 1x2:draw | 4459 | 23.2% | 24.7% | -1.4% | -14.7% ± 2.4% |
| 1x2:home | 4459 | 45.8% | 43.2% | +2.6% | -2.9% ± 2.0% |
| btts:no | 3824 | 44.8% | 45.9% | -1.1% | -10.1% ± 1.7% |
| btts:yes | 3824 | 55.2% | 54.1% | +1.1% | -6.1% ± 1.4% |
| dc:12 | 4263 | 76.7% | 74.5% | +2.2% | -4.9% ± 0.8% |
| dc:1x | 4263 | 68.9% | 67.7% | +1.3% | -7.4% ± 1.0% |
| dc:x2 | 4263 | 54.4% | 57.9% | -3.4% | -15.4% ± 1.3% |
| o/u1.5:over | 3379 | 76.2% | 74.4% | +1.8% | -4.2% ± 0.9% |
| o/u1.5:under | 3379 | 23.8% | 25.6% | -1.8% | -13.4% ± 2.8% |
| o/u2.5:over | 4199 | 56.2% | 53.9% | +2.3% | -3.1% ± 1.4% |
| o/u2.5:under | 4199 | 43.8% | 46.1% | -2.3% | -11.9% ± 1.6% |
| o/u3.5:over | 3853 | 37.1% | 36.1% | +1.0% | -4.8% ± 2.1% |
| o/u3.5:under | 3853 | 62.9% | 63.9% | -1.0% | -8.4% ± 1.2% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 359 | 83.3% | 78.1% | +5.2% | -1.3% ± 2.4% |
| 1x2 @ 1.30–1.60 | 824 | 67.1% | 63.6% | +3.5% | -2.6% ± 2.4% |
| 1x2 @ 1.60–2.00 | 1354 | 55.8% | 51.6% | +4.2% | -0.4% ± 2.4% |
| 1x2 @ 2.00–3.00 | 3257 | 38.9% | 37.7% | +1.2% | -5.4% ± 2.1% |
| 1x2 @ 3.00–5.00 | 5892 | 23.5% | 25.4% | -1.9% | -15.6% ± 2.0% |
| 1x2 @ 5.00–1000.00 | 1691 | 11.9% | 13.6% | -1.7% | -19.3% ± 5.8% |
| btts @ 1.00–1.30 | 76 | 71.1% | 73.2% | -2.2% | -11.7% ± 6.5% |
| btts @ 1.30–1.60 | 1572 | 59.7% | 61.6% | -1.8% | -11.3% ± 1.8% |
| btts @ 1.60–2.00 | 3541 | 51.3% | 51.3% | +0.0% | -8.7% ± 1.5% |
| btts @ 2.00–3.00 | 2346 | 41.6% | 40.6% | +1.0% | -5.8% ± 2.3% |
| btts @ 3.00–5.00 | 113 | 32.7% | 27.9% | +4.9% | +7.7% ± 14.7% |
| dc @ 1.00–1.30 | 5875 | 80.7% | 77.4% | +3.3% | -3.6% ± 0.6% |
| dc @ 1.30–1.60 | 4029 | 66.1% | 66.2% | -0.0% | -7.6% ± 1.0% |
| dc @ 1.60–2.00 | 1593 | 46.5% | 52.8% | -6.3% | -18.8% ± 2.2% |
| dc @ 2.00–3.00 | 991 | 34.1% | 40.0% | -5.9% | -21.2% ± 3.5% |
| dc @ 3.00–5.00 | 276 | 14.5% | 26.5% | -12.0% | -49.2% ± 7.5% |
| o/u1.5 @ 1.00–1.30 | 2232 | 80.3% | 78.4% | +1.9% | -4.1% ± 1.0% |
| o/u1.5 @ 1.30–1.60 | 1077 | 68.7% | 67.3% | +1.4% | -5.0% ± 2.0% |
| o/u1.5 @ 1.60–2.00 | 89 | 62.9% | 53.6% | +9.3% | +8.7% ± 9.0% |
| o/u1.5 @ 2.00–3.00 | 671 | 34.1% | 35.8% | -1.7% | -11.0% ± 4.8% |
| o/u1.5 @ 3.00–5.00 | 2107 | 22.6% | 24.9% | -2.3% | -15.0% ± 3.5% |
| o/u1.5 @ 5.00–1000.00 | 582 | 14.8% | 15.8% | -1.0% | -11.3% ± 9.0% |
| o/u2.5 @ 1.00–1.30 | 170 | 78.2% | 75.3% | +2.9% | -3.0% ± 4.0% |
| o/u2.5 @ 1.30–1.60 | 1707 | 64.3% | 63.3% | +1.1% | -5.4% ± 1.7% |
| o/u2.5 @ 1.60–2.00 | 3332 | 53.1% | 52.3% | +0.9% | -5.6% ± 1.5% |
| o/u2.5 @ 2.00–3.00 | 2816 | 39.3% | 40.7% | -1.4% | -10.0% ± 2.1% |
| o/u2.5 @ 3.00–5.00 | 357 | 24.6% | 28.0% | -3.3% | -16.0% ± 7.9% |
| o/u3.5 @ 1.00–1.30 | 923 | 75.0% | 75.8% | -0.8% | -8.2% ± 1.8% |
| o/u3.5 @ 1.30–1.60 | 1976 | 63.8% | 65.1% | -1.3% | -8.7% ± 1.6% |
| o/u3.5 @ 1.60–2.00 | 1290 | 54.9% | 52.9% | +2.0% | -3.3% ± 2.5% |
| o/u3.5 @ 2.00–3.00 | 2124 | 39.0% | 38.7% | +0.3% | -5.3% ± 2.6% |
| o/u3.5 @ 3.00–5.00 | 1328 | 26.9% | 26.5% | +0.3% | -5.4% ± 4.3% |
| o/u3.5 @ 5.00–1000.00 | 65 | 9.2% | 16.4% | -7.2% | -48.5% ± 20.2% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| USA · MLS — 1x2:draw | 38 | 42.1% | 23.1% | +19.0% | +72.4% ± 33.8% |
| Spain · Primera Federacion — dc:1x | 31 | 87.1% | 68.6% | +18.5% | +17.7% ± 8.6% |
| Sweden · Division 2 — dc:12 | 73 | 90.4% | 76.2% | +14.2% | +8.8% ± 4.2% |
| Spain · Segunda Federacion — dc:12 | 66 | 59.1% | 71.4% | -12.4% | -24.9% ± 7.8% |
| Sweden · Division 2 — dc:x2 | 73 | 47.9% | 57.2% | -9.3% | -26.0% ± 9.5% |
| USA · MLS — dc:12 | 38 | 57.9% | 75.8% | -17.9% | -28.1% ± 10.1% |
| England · Championship — dc:1x | 33 | 54.5% | 70.1% | -15.6% | -29.4% ± 11.6% |
| England · League One — dc:x2 | 33 | 42.4% | 54.6% | -12.2% | -31.9% ± 14.6% |
| USA · MLS — 1x2:home | 38 | 34.2% | 45.5% | -11.3% | -33.7% ± 15.7% |
| International Clubs · UEFA Champions League — o/u3.5:under | 36 | 36.1% | 52.3% | -16.2% | -34.2% ± 14.9% |
| Sweden · Division 2 — o/u3.5:under | 66 | 37.9% | 53.2% | -15.3% | -35.9% ± 10.3% |
| Sweden · Division 2 — o/u2.5:under | 65 | 23.1% | 34.4% | -11.3% | -37.2% ± 14.5% |
| Hungary · NB III — 1x2:away | 39 | 25.6% | 30.0% | -4.4% | -38.7% ± 19.1% |
| Spain · Segunda Federacion — 1x2:away | 66 | 19.7% | 28.7% | -9.0% | -38.9% ± 15.9% |
| USA · MLS — 1x2:away | 38 | 23.7% | 31.4% | -7.7% | -40.3% ± 18.6% |
| International Youth · UEFA Youth League — dc:x2 | 31 | 35.5% | 52.0% | -16.5% | -40.8% ± 16.0% |
| England Amateur · Southern League Premier Central — 1x2:away | 34 | 23.5% | 31.5% | -8.0% | -44.8% ± 18.0% |
| Spain · Primera Federacion — 1x2:away | 31 | 12.9% | 31.2% | -18.3% | -60.6% ± 19.2% |
| Sweden · Division 2 — 1x2:draw | 73 | 9.6% | 22.5% | -12.9% | -64.0% ± 13.0% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 1560 | -0.0% | -7.5% |
| not covered | 1x2 | 11817 | -0.0% | -11.3% |
| covered | btts | 1038 | +0.0% | -4.6% |
| not covered | btts | 6610 | +0.0% | -8.7% |
| covered | dc | 1560 | +0.0% | -7.5% |
| not covered | dc | 11229 | -0.0% | -9.5% |
| covered | o/u1.5 | 1032 | +0.0% | -6.7% |
| not covered | o/u1.5 | 5726 | +0.0% | -9.1% |
| covered | o/u2.5 | 1040 | +0.0% | -5.9% |
| not covered | o/u2.5 | 7358 | +0.0% | -7.7% |
| covered | o/u3.5 | 1040 | +0.0% | -5.3% |
| not covered | o/u3.5 | 6666 | +0.0% | -6.8% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 9241 | 48.3% | 48.1% | +0.1% | -0.0% ± 1.3% |
| steady | 28283 | 54.6% | 54.2% | +0.5% | -7.9% ± 0.6% |
| drifted 3%+ | 12140 | 39.0% | 40.2% | -1.2% | -19.4% ± 1.1% |

## Basketball — 892 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 889 | 50.2% | 50.1% | +0.1% | -7.1% ± 3.1% |
| hcp:home | 889 | 49.8% | 49.9% | -0.1% | -7.3% ± 3.1% |
| total:over | 887 | 53.1% | 50.1% | +3.0% | -1.6% ± 3.1% |
| total:under | 887 | 46.9% | 49.9% | -3.0% | -12.9% ± 3.1% |
| win:away | 885 | 42.1% | 42.5% | -0.3% | -10.3% ± 4.4% |
| win:home | 885 | 57.9% | 57.5% | +0.3% | -7.6% ± 3.3% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 1771 | 50.0% | 50.0% | +0.0% | -7.1% ± 2.2% |
| total @ 1.60–2.00 | 1773 | 50.0% | 50.0% | +0.0% | -7.2% ± 2.2% |
| win @ 1.00–1.30 | 351 | 82.6% | 82.4% | +0.2% | -6.9% ± 2.3% |
| win @ 1.30–1.60 | 318 | 66.0% | 65.9% | +0.1% | -6.4% ± 3.8% |
| win @ 1.60–2.00 | 283 | 49.5% | 53.0% | -3.5% | -12.2% ± 5.3% |
| win @ 2.00–3.00 | 374 | 42.5% | 39.2% | +3.3% | +1.1% ± 6.2% |
| win @ 3.00–5.00 | 249 | 28.9% | 25.9% | +3.0% | +6.5% ± 10.8% |
| win @ 5.00–1000.00 | 195 | 7.2% | 12.7% | -5.5% | -50.6% ± 13.3% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — win:away | 41 | 34.1% | 44.7% | -10.6% | -41.2% ± 13.6% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 94 | +0.0% | -6.1% |
| not covered | hcp | 1684 | +0.0% | -7.2% |
| covered | total | 94 | +0.0% | -6.3% |
| not covered | total | 1680 | +0.0% | -7.3% |
| covered | win | 94 | +0.0% | -4.1% |
| not covered | win | 1676 | +0.0% | -9.2% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 792 | 49.7% | 50.2% | -0.5% | +2.1% ± 4.4% |
| steady | 3260 | 51.9% | 51.7% | +0.2% | -6.6% ± 1.7% |
| drifted 3%+ | 864 | 42.9% | 43.2% | -0.3% | -19.1% ± 3.5% |

