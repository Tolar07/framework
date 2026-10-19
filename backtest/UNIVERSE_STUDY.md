# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

4839 games graded (81% of 5958 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-19.

## Football — 4105 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 4063 | 31.0% | 32.2% | -1.2% | -14.8% ± 2.4% |
| 1x2:draw | 4063 | 23.4% | 24.7% | -1.3% | -14.3% ± 2.5% |
| 1x2:home | 4063 | 45.6% | 43.1% | +2.5% | -3.5% ± 2.1% |
| btts:no | 3456 | 44.9% | 45.9% | -1.0% | -9.8% ± 1.8% |
| btts:yes | 3456 | 55.1% | 54.1% | +1.0% | -6.4% ± 1.5% |
| dc:12 | 3880 | 76.5% | 74.5% | +2.1% | -5.1% ± 0.9% |
| dc:1x | 3880 | 68.9% | 67.6% | +1.3% | -7.4% ± 1.1% |
| dc:x2 | 3880 | 54.6% | 57.9% | -3.3% | -15.2% ± 1.3% |
| o/u1.5:over | 3054 | 75.8% | 74.4% | +1.5% | -4.8% ± 1.0% |
| o/u1.5:under | 3054 | 24.2% | 25.6% | -1.5% | -12.2% ± 3.0% |
| o/u2.5:over | 3817 | 55.9% | 53.8% | +2.0% | -3.7% ± 1.4% |
| o/u2.5:under | 3817 | 44.1% | 46.2% | -2.0% | -11.7% ± 1.7% |
| o/u3.5:over | 3492 | 37.0% | 36.1% | +0.9% | -5.1% ± 2.2% |
| o/u3.5:under | 3492 | 63.0% | 63.9% | -0.9% | -8.3% ± 1.2% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 320 | 83.4% | 78.1% | +5.4% | -1.1% ± 2.5% |
| 1x2 @ 1.30–1.60 | 752 | 67.2% | 63.6% | +3.5% | -2.6% ± 2.5% |
| 1x2 @ 1.60–2.00 | 1233 | 55.6% | 51.6% | +4.0% | -0.8% ± 2.5% |
| 1x2 @ 2.00–3.00 | 2981 | 39.0% | 37.7% | +1.3% | -5.3% ± 2.2% |
| 1x2 @ 3.00–5.00 | 5383 | 23.5% | 25.4% | -1.9% | -15.6% ± 2.1% |
| 1x2 @ 5.00–1000.00 | 1520 | 11.8% | 13.6% | -1.8% | -19.1% ± 6.2% |
| btts @ 1.00–1.30 | 67 | 68.7% | 73.2% | -4.5% | -14.9% ± 7.1% |
| btts @ 1.30–1.60 | 1429 | 59.6% | 61.6% | -2.0% | -11.6% ± 1.9% |
| btts @ 1.60–2.00 | 3200 | 51.4% | 51.3% | +0.1% | -8.6% ± 1.6% |
| btts @ 2.00–3.00 | 2114 | 41.7% | 40.5% | +1.1% | -5.6% ± 2.4% |
| btts @ 3.00–5.00 | 102 | 33.3% | 27.9% | +5.4% | +9.7% ± 15.5% |
| dc @ 1.00–1.30 | 5354 | 80.5% | 77.3% | +3.2% | -3.8% ± 0.7% |
| dc @ 1.30–1.60 | 3669 | 66.4% | 66.1% | +0.2% | -7.3% ± 1.1% |
| dc @ 1.60–2.00 | 1446 | 46.5% | 52.8% | -6.3% | -18.7% ± 2.3% |
| dc @ 2.00–3.00 | 902 | 33.7% | 40.0% | -6.3% | -22.1% ± 3.7% |
| dc @ 3.00–5.00 | 247 | 14.2% | 26.5% | -12.3% | -50.1% ± 7.9% |
| o/u1.5 @ 1.00–1.30 | 2013 | 80.1% | 78.4% | +1.7% | -4.3% ± 1.1% |
| o/u1.5 @ 1.30–1.60 | 980 | 68.0% | 67.3% | +0.7% | -6.0% ± 2.1% |
| o/u1.5 @ 1.60–2.00 | 76 | 61.8% | 53.8% | +8.0% | +6.9% ± 9.8% |
| o/u1.5 @ 2.00–3.00 | 618 | 34.6% | 35.7% | -1.1% | -9.6% ± 5.0% |
| o/u1.5 @ 3.00–5.00 | 1898 | 23.0% | 24.9% | -1.8% | -13.3% ± 3.7% |
| o/u1.5 @ 5.00–1000.00 | 523 | 14.7% | 15.8% | -1.1% | -12.6% ± 9.4% |
| o/u2.5 @ 1.00–1.30 | 146 | 79.5% | 75.3% | +4.2% | -1.5% ± 4.2% |
| o/u2.5 @ 1.30–1.60 | 1558 | 64.7% | 63.2% | +1.5% | -4.8% ± 1.8% |
| o/u2.5 @ 1.60–2.00 | 3035 | 53.0% | 52.3% | +0.8% | -5.8% ± 1.6% |
| o/u2.5 @ 2.00–3.00 | 2568 | 39.3% | 40.8% | -1.5% | -10.3% ± 2.2% |
| o/u2.5 @ 3.00–5.00 | 313 | 23.6% | 28.1% | -4.4% | -19.6% ± 8.3% |
| o/u3.5 @ 1.00–1.30 | 843 | 74.6% | 75.7% | -1.1% | -8.7% ± 1.8% |
| o/u3.5 @ 1.30–1.60 | 1787 | 64.1% | 65.0% | -1.0% | -8.3% ± 1.6% |
| o/u3.5 @ 1.60–2.00 | 1173 | 55.2% | 52.9% | +2.4% | -2.7% ± 2.6% |
| o/u3.5 @ 2.00–3.00 | 1918 | 38.6% | 38.7% | -0.1% | -6.4% ± 2.7% |
| o/u3.5 @ 3.00–5.00 | 1205 | 27.0% | 26.5% | +0.4% | -5.1% ± 4.5% |
| o/u3.5 @ 5.00–1000.00 | 58 | 8.6% | 16.4% | -7.8% | -52.2% ± 20.6% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| USA · MLS — 1x2:draw | 37 | 43.2% | 23.1% | +20.1% | +77.1% ± 34.4% |
| Spain · Primera Federacion — dc:1x | 31 | 87.1% | 68.6% | +18.5% | +17.7% ± 8.6% |
| Sweden · Division 2 — dc:12 | 73 | 90.4% | 76.2% | +14.2% | +8.8% ± 4.2% |
| Sweden · Division 2 — dc:x2 | 73 | 47.9% | 57.2% | -9.3% | -26.0% ± 9.5% |
| Spain · Segunda Federacion — dc:12 | 64 | 57.8% | 71.4% | -13.6% | -26.5% ± 7.9% |
| USA · MLS — dc:12 | 37 | 56.8% | 75.8% | -19.1% | -29.5% ± 10.3% |
| England · Championship — dc:1x | 32 | 53.1% | 69.8% | -16.7% | -30.8% ± 11.8% |
| Sweden · Division 2 — o/u3.5:under | 66 | 37.9% | 53.2% | -15.3% | -35.9% ± 10.3% |
| Sweden · Division 2 — o/u2.5:under | 65 | 23.1% | 34.4% | -11.3% | -37.2% ± 14.5% |
| Hungary · NB III — 1x2:away | 39 | 25.6% | 30.0% | -4.4% | -38.7% ± 19.1% |
| Spain · Segunda Federacion — 1x2:away | 64 | 18.8% | 28.5% | -9.8% | -40.1% ± 16.2% |
| USA · MLS — 1x2:away | 37 | 21.6% | 31.3% | -9.6% | -46.1% ± 18.2% |
| Spain · Primera Federacion — 1x2:away | 31 | 12.9% | 31.2% | -18.3% | -60.6% ± 19.2% |
| Sweden · Division 2 — 1x2:draw | 73 | 9.6% | 22.5% | -12.9% | -64.0% ± 13.0% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 1365 | -0.0% | -7.0% |
| not covered | 1x2 | 10824 | -0.0% | -11.3% |
| covered | btts | 908 | +0.0% | -4.3% |
| not covered | btts | 6004 | +0.0% | -8.7% |
| covered | dc | 1365 | +0.0% | -7.3% |
| not covered | dc | 10275 | -0.0% | -9.5% |
| covered | o/u1.5 | 902 | +0.0% | -5.4% |
| not covered | o/u1.5 | 5206 | +0.0% | -9.0% |
| covered | o/u2.5 | 910 | +0.0% | -5.4% |
| not covered | o/u2.5 | 6724 | +0.0% | -8.0% |
| covered | o/u3.5 | 910 | +0.0% | -5.5% |
| not covered | o/u3.5 | 6074 | +0.0% | -6.8% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 8227 | 48.2% | 48.1% | +0.1% | -0.0% ± 1.4% |
| steady | 26150 | 54.5% | 54.0% | +0.4% | -7.9% ± 0.6% |
| drifted 3%+ | 10832 | 38.9% | 40.1% | -1.2% | -19.4% ± 1.1% |

## Basketball — 734 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 732 | 50.3% | 50.1% | +0.2% | -6.9% ± 3.4% |
| hcp:home | 732 | 49.7% | 49.9% | -0.2% | -7.6% ± 3.4% |
| total:over | 730 | 53.6% | 50.1% | +3.5% | -0.7% ± 3.4% |
| total:under | 730 | 46.4% | 49.9% | -3.5% | -13.8% ± 3.4% |
| win:away | 731 | 43.2% | 43.2% | +0.0% | -9.7% ± 4.7% |
| win:home | 731 | 56.8% | 56.8% | -0.0% | -8.7% ± 3.6% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 1458 | 50.1% | 50.0% | +0.1% | -7.1% ± 2.4% |
| total @ 1.60–2.00 | 1459 | 50.0% | 50.0% | +0.0% | -7.2% ± 2.4% |
| win @ 1.00–1.30 | 286 | 82.9% | 82.3% | +0.6% | -6.6% ± 2.6% |
| win @ 1.30–1.60 | 266 | 65.0% | 65.8% | -0.8% | -7.7% ± 4.2% |
| win @ 1.60–2.00 | 234 | 49.6% | 53.0% | -3.5% | -12.2% ± 5.8% |
| win @ 2.00–3.00 | 314 | 42.7% | 39.2% | +3.5% | +1.5% ± 6.7% |
| win @ 3.00–5.00 | 204 | 29.4% | 26.0% | +3.4% | +6.7% ± 11.8% |
| win @ 5.00–1000.00 | 158 | 7.0% | 12.8% | -5.8% | -53.4% ± 13.9% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — win:away | 41 | 34.1% | 44.7% | -10.6% | -41.2% ± 13.6% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 78 | +0.0% | -6.6% |
| not covered | hcp | 1386 | +0.0% | -7.3% |
| covered | total | 78 | +0.0% | -6.8% |
| not covered | total | 1382 | +0.0% | -7.3% |
| covered | win | 78 | +0.0% | -2.9% |
| not covered | win | 1384 | +0.0% | -9.5% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 654 | 50.3% | 50.2% | +0.1% | +2.2% ± 4.7% |
| steady | 2676 | 51.7% | 51.7% | -0.0% | -6.9% ± 1.8% |
| drifted 3%+ | 712 | 43.3% | 43.4% | -0.1% | -18.7% ± 3.9% |

