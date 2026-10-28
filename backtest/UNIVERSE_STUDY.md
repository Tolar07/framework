# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

8055 games graded (72% of 11170 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-28.

## Football — 6714 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 6615 | 31.5% | 32.2% | -0.7% | -13.8% ± 1.9% |
| 1x2:draw | 6615 | 23.7% | 24.7% | -1.0% | -13.2% ± 2.0% |
| 1x2:home | 6615 | 44.9% | 43.2% | +1.7% | -4.7% ± 1.6% |
| btts:no | 5644 | 44.1% | 45.8% | -1.7% | -11.5% ± 1.4% |
| btts:yes | 5644 | 55.9% | 54.2% | +1.7% | -5.3% ± 1.1% |
| dc:12 | 6306 | 76.5% | 74.5% | +2.0% | -5.2% ± 0.7% |
| dc:1x | 6306 | 68.4% | 67.7% | +0.7% | -8.1% ± 0.8% |
| dc:x2 | 6306 | 55.1% | 57.8% | -2.7% | -14.1% ± 1.1% |
| o/u1.5:over | 5013 | 76.9% | 74.5% | +2.4% | -3.6% ± 0.8% |
| o/u1.5:under | 5013 | 23.1% | 25.5% | -2.4% | -16.0% ± 2.3% |
| o/u2.5:over | 6225 | 56.2% | 54.0% | +2.3% | -3.1% ± 1.1% |
| o/u2.5:under | 6225 | 43.8% | 46.0% | -2.3% | -12.2% ± 1.3% |
| o/u3.5:over | 5695 | 37.2% | 36.2% | +1.1% | -5.2% ± 1.7% |
| o/u3.5:under | 5695 | 62.8% | 63.8% | -1.1% | -8.7% ± 1.0% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 518 | 83.4% | 78.2% | +5.2% | -1.5% ± 2.0% |
| 1x2 @ 1.30–1.60 | 1240 | 67.7% | 63.6% | +4.2% | -1.6% ± 1.9% |
| 1x2 @ 1.60–2.00 | 1983 | 53.9% | 51.6% | +2.3% | -3.7% ± 2.0% |
| 1x2 @ 2.00–3.00 | 4850 | 38.8% | 37.8% | +1.0% | -5.6% ± 1.7% |
| 1x2 @ 3.00–5.00 | 8786 | 24.1% | 25.4% | -1.3% | -13.0% ± 1.7% |
| 1x2 @ 5.00–1000.00 | 2468 | 11.3% | 13.6% | -2.3% | -23.9% ± 4.7% |
| btts @ 1.00–1.30 | 106 | 72.6% | 73.2% | -0.6% | -9.7% ± 5.4% |
| btts @ 1.30–1.60 | 2345 | 61.1% | 61.6% | -0.5% | -9.2% ± 1.5% |
| btts @ 1.60–2.00 | 5185 | 51.4% | 51.3% | +0.1% | -8.4% ± 1.2% |
| btts @ 2.00–3.00 | 3493 | 40.6% | 40.6% | +0.0% | -8.2% ± 1.9% |
| btts @ 3.00–5.00 | 159 | 30.8% | 27.9% | +3.0% | +2.0% ± 12.2% |
| dc @ 1.00–1.30 | 8675 | 80.5% | 77.4% | +3.1% | -3.9% ± 0.5% |
| dc @ 1.30–1.60 | 5963 | 66.0% | 66.2% | -0.2% | -7.8% ± 0.9% |
| dc @ 1.60–2.00 | 2359 | 47.8% | 52.9% | -5.1% | -16.5% ± 1.8% |
| dc @ 2.00–3.00 | 1492 | 34.2% | 40.1% | -5.9% | -21.5% ± 2.8% |
| dc @ 3.00–5.00 | 396 | 14.6% | 26.3% | -11.7% | -47.7% ± 6.4% |
| dc @ 5.00–1000.00 | 33 | 6.1% | 16.6% | -10.5% | -68.2% ± 22.2% |
| o/u1.5 @ 1.00–1.30 | 3355 | 80.8% | 78.4% | +2.4% | -3.5% ± 0.8% |
| o/u1.5 @ 1.30–1.60 | 1557 | 69.6% | 67.3% | +2.2% | -3.9% ± 1.6% |
| o/u1.5 @ 1.60–2.00 | 122 | 60.7% | 54.2% | +6.5% | +3.9% ± 7.7% |
| o/u1.5 @ 2.00–3.00 | 968 | 33.2% | 35.8% | -2.6% | -14.2% ± 3.9% |
| o/u1.5 @ 3.00–5.00 | 3146 | 22.6% | 24.8% | -2.3% | -15.0% ± 2.8% |
| o/u1.5 @ 5.00–1000.00 | 878 | 13.0% | 15.9% | -2.9% | -22.5% ± 6.9% |
| o/u2.5 @ 1.00–1.30 | 237 | 80.6% | 75.4% | +5.2% | -0.3% ± 3.2% |
| o/u2.5 @ 1.30–1.60 | 2518 | 64.6% | 63.3% | +1.3% | -5.0% ± 1.4% |
| o/u2.5 @ 1.60–2.00 | 4950 | 53.1% | 52.3% | +0.7% | -5.8% ± 1.3% |
| o/u2.5 @ 2.00–3.00 | 4220 | 39.4% | 40.8% | -1.4% | -10.0% ± 1.7% |
| o/u2.5 @ 3.00–5.00 | 504 | 23.2% | 27.9% | -4.7% | -21.5% ± 6.4% |
| o/u3.5 @ 1.00–1.30 | 1319 | 75.9% | 75.7% | +0.2% | -7.0% ± 1.4% |
| o/u3.5 @ 1.30–1.60 | 2963 | 64.7% | 65.1% | -0.3% | -7.2% ± 1.3% |
| o/u3.5 @ 1.60–2.00 | 1894 | 53.5% | 53.0% | +0.5% | -5.8% ± 2.0% |
| o/u3.5 @ 2.00–3.00 | 3216 | 39.0% | 38.6% | +0.4% | -5.4% ± 2.1% |
| o/u3.5 @ 3.00–5.00 | 1908 | 26.2% | 26.6% | -0.4% | -8.3% ± 3.6% |
| o/u3.5 @ 5.00–1000.00 | 90 | 8.9% | 16.5% | -7.7% | -50.9% ± 16.7% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · J3 League — dc:12 | 32 | 90.6% | 72.6% | +18.0% | +15.6% ± 6.7% |
| Portugal · Campeonato de Portugal — dc:1x | 47 | 61.7% | 69.7% | -8.0% | -19.5% ± 9.7% |
| England · Championship — dc:1x | 44 | 59.1% | 68.8% | -9.7% | -20.7% ± 10.3% |
| Spain · Segunda Federacion — dc:12 | 100 | 62.0% | 71.7% | -9.7% | -21.5% ± 6.2% |
| USA · MLS — dc:12 | 54 | 63.0% | 75.8% | -12.9% | -21.7% ± 8.3% |
| England Amateur · National League South — dc:1x | 38 | 60.5% | 67.5% | -7.0% | -22.2% ± 10.6% |
| Italy · Serie B — dc:1x | 36 | 58.3% | 69.4% | -11.1% | -22.7% ± 11.3% |
| Sweden · Division 2 — dc:x2 | 75 | 49.3% | 57.3% | -8.0% | -24.0% ± 9.3% |
| China · China League 2 — dc:12 | 33 | 57.6% | 70.5% | -12.9% | -25.6% ± 11.3% |
| Portugal · Campeonato de Portugal — btts:no | 47 | 42.6% | 51.5% | -8.9% | -25.9% ± 12.7% |
| Sweden · Division 2 — btts:no | 68 | 30.9% | 36.8% | -5.9% | -27.0% ± 13.5% |
| Romania · Liga 3 — dc:x2 | 42 | 45.2% | 54.9% | -9.7% | -28.5% ± 13.3% |
| Italy · Serie A — dc:x2 | 32 | 50.0% | 58.2% | -8.2% | -28.6% ± 13.4% |
| Turkiye · 1. Lig — dc:1x | 39 | 53.8% | 67.4% | -13.6% | -28.8% ± 10.9% |
| England Amateur · Southern League Premier Central — btts:no | 47 | 34.0% | 43.5% | -9.4% | -29.9% ± 14.5% |
| Hungary · NB III — 1x2:away | 56 | 30.4% | 31.8% | -1.5% | -31.9% ± 15.5% |
| England · League One — dc:x2 | 48 | 43.8% | 56.0% | -12.3% | -32.7% ± 11.5% |
| Sweden · Division 2 — o/u3.5:under | 68 | 39.7% | 53.4% | -13.7% | -33.3% ± 10.1% |
| International Clubs · UEFA Champions League — o/u3.5:under | 36 | 36.1% | 52.3% | -16.2% | -34.2% ± 14.9% |
| Turkiye · 1. Lig — 1x2:home | 39 | 33.3% | 41.5% | -8.2% | -34.8% ± 15.6% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 2382 | -0.0% | -6.8% |
| not covered | 1x2 | 17463 | +0.0% | -11.1% |
| covered | btts | 1584 | +0.0% | -5.3% |
| not covered | btts | 9704 | +0.0% | -8.9% |
| covered | dc | 2382 | +0.0% | -7.3% |
| not covered | dc | 16536 | +0.0% | -9.4% |
| covered | o/u1.5 | 1576 | +0.0% | -8.0% |
| not covered | o/u1.5 | 8450 | +0.0% | -10.1% |
| covered | o/u2.5 | 1588 | +0.0% | -5.7% |
| not covered | o/u2.5 | 10862 | +0.0% | -7.9% |
| covered | o/u3.5 | 1588 | +0.0% | -5.8% |
| not covered | o/u3.5 | 9802 | +0.0% | -7.2% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 13784 | 48.8% | 48.4% | +0.4% | +0.6% ± 1.1% |
| steady | 40833 | 54.6% | 54.2% | +0.4% | -8.0% ± 0.5% |
| drifted 3%+ | 18202 | 39.0% | 40.2% | -1.2% | -19.7% ± 0.9% |

## Basketball — 1341 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 1335 | 50.3% | 50.1% | +0.2% | -6.8% ± 2.5% |
| hcp:home | 1335 | 49.7% | 49.9% | -0.2% | -7.5% ± 2.5% |
| total:over | 1335 | 50.3% | 50.1% | +0.2% | -6.8% ± 2.5% |
| total:under | 1335 | 49.7% | 49.9% | -0.2% | -7.6% ± 2.5% |
| win:away | 1334 | 42.2% | 43.0% | -0.8% | -11.5% ± 3.6% |
| win:home | 1334 | 57.8% | 57.0% | +0.8% | -6.5% ± 2.7% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 2659 | 50.1% | 50.0% | +0.1% | -7.0% ± 1.8% |
| total @ 1.60–2.00 | 2669 | 50.0% | 50.0% | +0.0% | -7.1% ± 1.8% |
| win @ 1.00–1.30 | 538 | 82.9% | 82.4% | +0.5% | -6.4% ± 1.9% |
| win @ 1.30–1.60 | 453 | 65.3% | 65.9% | -0.6% | -7.6% ± 3.2% |
| win @ 1.60–2.00 | 440 | 49.8% | 53.2% | -3.5% | -12.0% ± 4.2% |
| win @ 2.00–3.00 | 565 | 43.7% | 39.6% | +4.2% | +3.3% ± 5.0% |
| win @ 3.00–5.00 | 380 | 27.1% | 25.6% | +1.5% | -0.0% ± 8.5% |
| win @ 5.00–1000.00 | 292 | 7.9% | 12.6% | -4.7% | -46.6% ± 11.0% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — hcp:away | 64 | 42.2% | 50.1% | -7.9% | -23.5% ± 11.3% |
| Japan · B League One — total:over | 64 | 40.6% | 50.1% | -9.4% | -25.9% ± 11.3% |
| Japan · B League One — win:away | 64 | 35.9% | 46.0% | -10.0% | -33.1% ± 13.1% |
| Italy · Serie A2 — hcp:away | 34 | 35.3% | 49.9% | -14.6% | -35.6% ± 15.2% |
| International · Euroleague — hcp:home | 30 | 33.3% | 50.3% | -17.0% | -37.0% ± 16.6% |
| International · Euroleague — win:home | 30 | 43.3% | 60.6% | -17.2% | -38.9% ± 13.3% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 164 | +0.0% | -5.3% |
| not covered | hcp | 2506 | +0.0% | -7.3% |
| covered | total | 164 | +0.0% | -5.3% |
| not covered | total | 2506 | +0.0% | -7.3% |
| covered | win | 164 | +0.0% | -6.6% |
| not covered | win | 2504 | +0.0% | -9.1% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 1202 | 50.0% | 50.2% | -0.2% | +2.1% ± 3.5% |
| steady | 4927 | 51.9% | 51.7% | +0.2% | -6.8% ± 1.4% |
| drifted 3%+ | 1323 | 42.9% | 43.4% | -0.5% | -18.8% ± 2.9% |

