# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

117 games graded (100% of 117 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-08.

## Football — 78 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 71 | 25.4% | 31.8% | -6.5% | -38.5% ± 14.8% |
| 1x2:draw | 71 | 25.4% | 25.4% | -0.0% | -8.8% ± 19.4% |
| 1x2:home | 71 | 49.3% | 42.8% | +6.5% | +18.6% ± 18.3% |
| btts:no | 67 | 53.7% | 50.8% | +3.0% | -3.4% ± 11.4% |
| btts:yes | 67 | 46.3% | 49.2% | -3.0% | -15.1% ± 11.5% |
| dc:12 | 70 | 74.3% | 36.9% | +37.3% | -7.6% ± 6.6% |
| dc:1x | 70 | 74.3% | 33.7% | +40.6% | -0.6% ± 7.7% |
| dc:x2 | 70 | 51.4% | 29.3% | +22.1% | -17.5% ± 10.4% |
| o/u1.5:over | 61 | 72.1% | 70.1% | +2.1% | -4.2% ± 7.8% |
| o/u1.5:under | 61 | 27.9% | 29.9% | -2.1% | -13.9% ± 18.4% |
| o/u2.5:over | 68 | 57.4% | 49.2% | +8.1% | +8.6% ± 12.0% |
| o/u2.5:under | 68 | 42.6% | 50.8% | -8.1% | -21.9% ± 11.7% |
| o/u3.5:over | 63 | 38.1% | 30.9% | +7.2% | +22.7% ± 21.4% |
| o/u3.5:under | 63 | 61.9% | 69.1% | -7.2% | -15.8% ± 8.7% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 2.00–3.00 | 39 | 43.6% | 37.3% | +6.3% | +6.0% ± 19.8% |
| 1x2 @ 3.00–5.00 | 95 | 23.2% | 25.4% | -2.3% | -17.7% ± 15.7% |
| 1x2 @ 5.00–1000.00 | 31 | 16.1% | 14.2% | +1.9% | -0.2% ± 41.9% |
| btts @ 1.30–1.60 | 31 | 58.1% | 60.6% | -2.6% | -13.8% ± 13.4% |
| btts @ 1.60–2.00 | 62 | 48.4% | 50.9% | -2.5% | -14.5% ± 11.3% |
| btts @ 2.00–3.00 | 41 | 46.3% | 40.6% | +5.8% | +2.0% ± 17.4% |
| dc @ 1.00–1.30 | 101 | 80.2% | 38.7% | +41.5% | -4.6% ± 4.8% |
| dc @ 1.30–1.60 | 58 | 63.8% | 33.2% | +30.6% | -11.4% ± 8.9% |
| dc @ 1.60–2.00 | 30 | 43.3% | 25.8% | +17.5% | -23.7% ± 16.2% |
| o/u1.5 @ 1.30–1.60 | 30 | 70.0% | 66.2% | +3.8% | -1.5% ± 12.0% |
| o/u1.5 @ 3.00–5.00 | 31 | 29.0% | 25.5% | +3.5% | +3.4% ± 29.9% |
| o/u2.5 @ 1.30–1.60 | 34 | 58.8% | 62.9% | -4.1% | -13.4% ± 12.7% |
| o/u2.5 @ 1.60–2.00 | 48 | 54.2% | 51.8% | +2.3% | -4.8% ± 12.8% |
| o/u2.5 @ 2.00–3.00 | 48 | 41.7% | 39.8% | +1.8% | -1.7% ± 17.2% |
| o/u3.5 @ 1.00–1.30 | 31 | 64.5% | 76.9% | -12.4% | -22.1% ± 10.6% |
| o/u3.5 @ 3.00–5.00 | 32 | 34.4% | 25.0% | +9.4% | +34.5% ± 33.8% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| not covered | 1x2 | 213 | -0.0% | -9.6% |
| not covered | btts | 134 | +0.0% | -9.3% |
| not covered | dc | 210 | +33.3% | -8.6% |
| not covered | o/u1.5 | 122 | +0.0% | -9.0% |
| not covered | o/u2.5 | 136 | +0.0% | -6.6% |
| not covered | o/u3.5 | 126 | +0.0% | +3.4% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 130 | 56.2% | 42.2% | +13.9% | +12.5% ± 10.6% |
| steady | 429 | 53.6% | 44.9% | +8.7% | -4.9% ± 5.1% |
| drifted 3%+ | 141 | 32.6% | 33.6% | -0.9% | -28.3% ± 10.2% |

## Basketball — 39 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 38 | 50.0% | 50.3% | -0.3% | -7.4% ± 15.2% |
| hcp:home | 38 | 50.0% | 49.7% | +0.3% | -5.6% ± 15.5% |
| total:over | 38 | 55.3% | 50.0% | +5.3% | +3.6% ± 15.3% |
| total:under | 38 | 44.7% | 50.0% | -5.3% | -17.2% ± 15.1% |
| win:away | 39 | 33.3% | 41.3% | -8.0% | -37.5% ± 17.1% |
| win:home | 39 | 66.7% | 58.7% | +8.0% | -2.1% ± 12.4% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 75 | 50.7% | 50.0% | +0.6% | -5.3% ± 10.9% |
| total @ 1.60–2.00 | 76 | 50.0% | 50.0% | +0.0% | -6.8% ± 10.8% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 8 | +0.0% | -7.1% |
| not covered | hcp | 68 | +0.0% | -6.5% |
| covered | total | 8 | +0.0% | -7.1% |
| not covered | total | 68 | +0.0% | -6.8% |
| covered | win | 8 | +0.0% | +22.8% |
| not covered | win | 70 | +0.0% | -24.7% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 20 | 65.0% | 52.9% | +12.1% | +31.2% ± 28.2% |
| steady | 89 | 51.7% | 51.2% | +0.5% | -5.8% ± 9.9% |
| drifted 3%+ | 23 | 30.4% | 42.9% | -12.5% | -44.5% ± 18.7% |

