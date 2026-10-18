# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

4048 games graded (84% of 4811 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-18.

## Football — 3399 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 3369 | 31.3% | 32.3% | -1.0% | -13.2% ± 2.7% |
| 1x2:draw | 3369 | 22.9% | 24.6% | -1.7% | -15.3% ± 2.8% |
| 1x2:home | 3369 | 45.7% | 43.1% | +2.7% | -2.8% ± 2.3% |
| btts:no | 2909 | 45.1% | 45.7% | -0.6% | -8.9% ± 1.9% |
| btts:yes | 2909 | 54.9% | 54.3% | +0.6% | -7.0% ± 1.6% |
| dc:12 | 3261 | 77.0% | 74.5% | +2.6% | -4.5% ± 0.9% |
| dc:1x | 3261 | 68.6% | 67.5% | +1.1% | -7.4% ± 1.2% |
| dc:x2 | 3261 | 54.4% | 58.0% | -3.6% | -15.6% ± 1.5% |
| o/u1.5:over | 2568 | 76.5% | 74.5% | +2.1% | -3.9% ± 1.1% |
| o/u1.5:under | 2568 | 23.5% | 25.5% | -2.1% | -14.1% ± 3.2% |
| o/u2.5:over | 3162 | 55.6% | 54.1% | +1.5% | -4.3% ± 1.6% |
| o/u2.5:under | 3162 | 44.4% | 45.9% | -1.5% | -10.3% ± 1.9% |
| o/u3.5:over | 2948 | 36.4% | 36.2% | +0.2% | -6.4% ± 2.4% |
| o/u3.5:under | 2948 | 63.6% | 63.8% | -0.2% | -7.0% ± 1.4% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 274 | 81.4% | 78.0% | +3.4% | -3.4% ± 2.8% |
| 1x2 @ 1.30–1.60 | 609 | 68.6% | 63.6% | +5.1% | -0.2% ± 2.8% |
| 1x2 @ 1.60–2.00 | 1014 | 55.1% | 51.6% | +3.5% | -1.7% ± 2.8% |
| 1x2 @ 2.00–3.00 | 2505 | 38.5% | 37.7% | +0.8% | -6.2% ± 2.4% |
| 1x2 @ 3.00–5.00 | 4451 | 23.6% | 25.4% | -1.7% | -15.0% ± 2.3% |
| 1x2 @ 5.00–1000.00 | 1254 | 12.1% | 13.6% | -1.5% | -16.2% ± 7.0% |
| btts @ 1.00–1.30 | 54 | 66.7% | 73.4% | -6.7% | -17.3% ± 8.0% |
| btts @ 1.30–1.60 | 1229 | 59.6% | 61.5% | -1.9% | -11.5% ± 2.1% |
| btts @ 1.60–2.00 | 2647 | 51.2% | 51.3% | -0.1% | -8.9% ± 1.7% |
| btts @ 2.00–3.00 | 1804 | 41.9% | 40.6% | +1.3% | -5.2% ± 2.7% |
| btts @ 3.00–5.00 | 84 | 35.7% | 27.9% | +7.8% | +18.1% ± 17.5% |
| dc @ 1.00–1.30 | 4479 | 80.6% | 77.3% | +3.3% | -3.6% ± 0.7% |
| dc @ 1.30–1.60 | 3120 | 66.0% | 66.1% | -0.1% | -7.7% ± 1.2% |
| dc @ 1.60–2.00 | 1214 | 47.2% | 52.8% | -5.6% | -17.5% ± 2.5% |
| dc @ 2.00–3.00 | 742 | 32.7% | 40.0% | -7.3% | -24.2% ± 4.0% |
| dc @ 3.00–5.00 | 208 | 15.9% | 26.6% | -10.7% | -44.2% ± 9.0% |
| o/u1.5 @ 1.00–1.30 | 1698 | 80.4% | 78.5% | +1.9% | -4.0% ± 1.2% |
| o/u1.5 @ 1.30–1.60 | 818 | 69.6% | 67.3% | +2.3% | -3.8% ± 2.2% |
| o/u1.5 @ 1.60–2.00 | 65 | 61.5% | 53.9% | +7.7% | +6.5% ± 10.6% |
| o/u1.5 @ 2.00–3.00 | 510 | 32.9% | 35.7% | -2.8% | -14.0% ± 5.5% |
| o/u1.5 @ 3.00–5.00 | 1596 | 22.8% | 24.9% | -2.1% | -13.7% ± 4.0% |
| o/u1.5 @ 5.00–1000.00 | 449 | 13.8% | 15.8% | -2.0% | -17.6% ± 9.9% |
| o/u2.5 @ 1.00–1.30 | 126 | 78.6% | 75.5% | +3.1% | -2.8% ± 4.6% |
| o/u2.5 @ 1.30–1.60 | 1304 | 63.4% | 63.2% | +0.2% | -6.7% ± 2.0% |
| o/u2.5 @ 1.60–2.00 | 2472 | 52.8% | 52.3% | +0.5% | -6.1% ± 1.8% |
| o/u2.5 @ 2.00–3.00 | 2144 | 40.3% | 40.7% | -0.4% | -7.9% ± 2.4% |
| o/u2.5 @ 3.00–5.00 | 266 | 24.4% | 28.0% | -3.5% | -16.4% ± 9.1% |
| o/u3.5 @ 1.00–1.30 | 701 | 74.3% | 75.8% | -1.4% | -9.0% ± 2.0% |
| o/u3.5 @ 1.30–1.60 | 1505 | 64.9% | 65.1% | -0.1% | -6.9% ± 1.8% |
| o/u3.5 @ 1.60–2.00 | 1004 | 55.1% | 52.9% | +2.1% | -3.2% ± 2.8% |
| o/u3.5 @ 2.00–3.00 | 1632 | 37.7% | 38.7% | -1.0% | -8.6% ± 2.9% |
| o/u3.5 @ 3.00–5.00 | 1005 | 27.6% | 26.5% | +1.0% | -2.8% ± 5.0% |
| o/u3.5 @ 5.00–1000.00 | 49 | 8.2% | 16.3% | -8.2% | -54.3% ± 22.1% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| USA · MLS — 1x2:draw | 32 | 46.9% | 23.1% | +23.8% | +93.6% ± 37.7% |
| England · Championship — dc:1x | 32 | 53.1% | 69.8% | -16.7% | -30.8% ± 11.8% |
| USA · MLS — dc:12 | 32 | 53.1% | 75.8% | -22.7% | -34.0% ± 11.2% |
| USA · MLS — 1x2:home | 32 | 34.4% | 46.1% | -11.7% | -34.5% ± 16.9% |
| USA · MLS — btts:no | 32 | 21.9% | 37.0% | -15.1% | -44.6% ± 19.0% |
| Spain · Segunda Federacion — 1x2:away | 42 | 16.7% | 28.1% | -11.5% | -45.4% ± 19.3% |
| Hungary · NB III — 1x2:away | 36 | 25.0% | 30.2% | -5.2% | -46.8% ± 16.9% |
| USA · MLS — 1x2:away | 32 | 18.8% | 30.8% | -12.0% | -57.2% ± 16.3% |
| Sweden · Division 2 — 1x2:draw | 53 | 11.3% | 22.5% | -11.2% | -57.5% ± 16.5% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 1191 | +0.0% | -7.0% |
| not covered | 1x2 | 8916 | -0.0% | -10.9% |
| covered | btts | 792 | +0.0% | -4.0% |
| not covered | btts | 5026 | +0.0% | -8.6% |
| covered | dc | 1191 | +0.0% | -7.2% |
| not covered | dc | 8592 | +0.0% | -9.4% |
| covered | o/u1.5 | 786 | +0.0% | -3.4% |
| not covered | o/u1.5 | 4350 | +0.0% | -10.1% |
| covered | o/u2.5 | 794 | +0.0% | -5.1% |
| not covered | o/u2.5 | 5530 | +0.0% | -7.6% |
| covered | o/u3.5 | 794 | +0.0% | -5.5% |
| not covered | o/u3.5 | 5102 | +0.0% | -6.9% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 6866 | 48.0% | 48.0% | -0.0% | -0.2% ± 1.5% |
| steady | 22228 | 54.5% | 54.1% | +0.4% | -7.9% ± 0.7% |
| drifted 3%+ | 9103 | 39.0% | 40.0% | -1.0% | -18.9% ± 1.3% |

## Basketball — 649 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 647 | 50.7% | 50.1% | +0.6% | -6.1% ± 3.6% |
| hcp:home | 647 | 49.3% | 49.9% | -0.6% | -8.3% ± 3.7% |
| total:over | 645 | 53.2% | 50.1% | +3.1% | -1.4% ± 3.6% |
| total:under | 645 | 46.8% | 49.9% | -3.1% | -13.1% ± 3.7% |
| win:away | 647 | 44.2% | 43.6% | +0.6% | -7.3% ± 5.1% |
| win:home | 647 | 55.8% | 56.4% | -0.6% | -10.3% ± 3.8% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 1288 | 50.1% | 50.0% | +0.1% | -7.1% ± 2.6% |
| total @ 1.60–2.00 | 1289 | 50.0% | 50.0% | +0.0% | -7.2% ± 2.6% |
| win @ 1.00–1.30 | 247 | 82.6% | 82.2% | +0.4% | -6.7% ± 2.8% |
| win @ 1.30–1.60 | 242 | 65.7% | 65.8% | -0.1% | -6.9% ± 4.4% |
| win @ 1.60–2.00 | 205 | 48.3% | 53.1% | -4.9% | -14.5% ± 6.2% |
| win @ 2.00–3.00 | 282 | 43.3% | 39.2% | +4.0% | +2.3% ± 7.1% |
| win @ 3.00–5.00 | 185 | 28.6% | 26.0% | +2.7% | +4.5% ± 12.3% |
| win @ 5.00–1000.00 | 133 | 7.5% | 12.9% | -5.4% | -49.0% ± 16.0% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — win:away | 40 | 35.0% | 45.2% | -10.2% | -39.7% ± 13.8% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 78 | +0.0% | -6.6% |
| not covered | hcp | 1216 | +0.0% | -7.2% |
| covered | total | 78 | +0.0% | -6.8% |
| not covered | total | 1212 | +0.0% | -7.3% |
| covered | win | 78 | +0.0% | -2.9% |
| not covered | win | 1216 | +0.0% | -9.1% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 578 | 50.2% | 50.2% | +0.0% | +2.5% ± 5.1% |
| steady | 2359 | 51.6% | 51.7% | -0.1% | -7.0% ± 2.0% |
| drifted 3%+ | 629 | 43.9% | 43.6% | +0.2% | -17.5% ± 4.1% |

