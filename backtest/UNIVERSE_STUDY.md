# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

148 games graded (100% of 148 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-09.

## Football — 97 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 90 | 23.3% | 31.8% | -8.4% | -46.2% ± 12.1% |
| 1x2:draw | 90 | 27.8% | 25.3% | +2.5% | -3.0% ± 17.1% |
| 1x2:home | 90 | 48.9% | 43.0% | +5.9% | +12.4% ± 15.4% |
| btts:no | 84 | 54.8% | 50.4% | +4.3% | -0.7% ± 10.2% |
| btts:yes | 84 | 45.2% | 49.6% | -4.3% | -17.4% ± 10.2% |
| dc:12 | 89 | 71.9% | 37.0% | +34.9% | -11.0% ± 6.0% |
| dc:1x | 89 | 76.4% | 33.8% | +42.6% | +1.6% ± 6.6% |
| dc:x2 | 89 | 51.7% | 29.2% | +22.5% | -18.9% ± 9.0% |
| o/u1.5:over | 78 | 70.5% | 70.6% | -0.1% | -6.7% ± 7.0% |
| o/u1.5:under | 78 | 29.5% | 29.4% | +0.1% | -4.6% ± 17.4% |
| o/u2.5:over | 86 | 53.5% | 49.7% | +3.8% | -0.0% ± 10.5% |
| o/u2.5:under | 86 | 46.5% | 50.3% | -3.8% | -13.5% ± 10.6% |
| o/u3.5:over | 80 | 33.8% | 31.1% | +2.6% | +7.4% ± 18.1% |
| o/u3.5:under | 80 | 66.2% | 68.9% | -2.6% | -9.5% ± 7.5% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.60–2.00 | 34 | 44.1% | 51.5% | -7.3% | -22.7% ± 15.2% |
| 1x2 @ 2.00–3.00 | 48 | 43.8% | 37.2% | +6.5% | +7.3% ± 18.0% |
| 1x2 @ 3.00–5.00 | 119 | 23.5% | 25.3% | -1.8% | -16.8% ± 14.0% |
| 1x2 @ 5.00–1000.00 | 41 | 12.2% | 14.4% | -2.2% | -24.5% ± 32.2% |
| btts @ 1.30–1.60 | 34 | 61.8% | 60.5% | +1.2% | -7.8% ± 12.6% |
| btts @ 1.60–2.00 | 86 | 46.5% | 50.9% | -4.4% | -16.8% ± 9.7% |
| btts @ 2.00–3.00 | 48 | 47.9% | 40.9% | +7.0% | +4.1% ± 15.9% |
| dc @ 1.00–1.30 | 129 | 82.2% | 38.8% | +43.3% | -2.5% ± 4.1% |
| dc @ 1.30–1.60 | 71 | 62.0% | 33.3% | +28.7% | -14.1% ± 8.1% |
| dc @ 1.60–2.00 | 37 | 48.6% | 26.0% | +22.6% | -14.7% ± 14.7% |
| o/u1.5 @ 1.00–1.30 | 37 | 73.0% | 76.8% | -3.8% | -11.7% ± 9.0% |
| o/u1.5 @ 1.30–1.60 | 36 | 69.4% | 66.1% | +3.4% | -2.1% ± 11.0% |
| o/u1.5 @ 2.00–3.00 | 31 | 29.0% | 36.7% | -7.6% | -26.5% ± 21.1% |
| o/u1.5 @ 3.00–5.00 | 43 | 32.6% | 25.4% | +7.2% | +20.0% ± 27.1% |
| o/u2.5 @ 1.30–1.60 | 38 | 57.9% | 63.0% | -5.1% | -14.9% ± 12.0% |
| o/u2.5 @ 1.60–2.00 | 69 | 55.1% | 51.9% | +3.1% | -3.1% ± 10.6% |
| o/u2.5 @ 2.00–3.00 | 59 | 40.7% | 40.1% | +0.6% | -4.2% ± 15.4% |
| o/u3.5 @ 1.00–1.30 | 35 | 68.6% | 77.0% | -8.4% | -17.1% ± 9.7% |
| o/u3.5 @ 1.30–1.60 | 35 | 62.9% | 65.5% | -2.6% | -11.5% ± 11.7% |
| o/u3.5 @ 2.00–3.00 | 31 | 41.9% | 37.4% | +4.5% | +4.0% ± 22.5% |
| o/u3.5 @ 3.00–5.00 | 39 | 30.8% | 25.4% | +5.4% | +18.6% ± 29.2% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 3 | +0.0% | -55.7% |
| not covered | 1x2 | 267 | +0.0% | -11.8% |
| covered | btts | 2 | +0.0% | -11.5% |
| not covered | btts | 166 | +0.0% | -9.0% |
| covered | dc | 3 | +33.3% | -25.7% |
| not covered | dc | 264 | +33.3% | -9.3% |
| covered | o/u1.5 | 2 | +0.0% | +125.0% |
| not covered | o/u1.5 | 154 | +0.0% | -7.4% |
| covered | o/u2.5 | 2 | +0.0% | +15.0% |
| not covered | o/u2.5 | 170 | +0.0% | -7.0% |
| covered | o/u3.5 | 2 | +0.0% | -24.5% |
| not covered | o/u3.5 | 158 | +0.0% | -0.7% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 177 | 50.8% | 43.0% | +7.8% | +0.6% ± 8.8% |
| steady | 563 | 53.8% | 44.8% | +9.0% | -6.7% ± 4.3% |
| drifted 3%+ | 203 | 37.9% | 34.2% | +3.7% | -19.1% ± 8.5% |

## Basketball — 51 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 50 | 52.0% | 50.4% | +1.6% | -3.6% ± 13.2% |
| hcp:home | 50 | 48.0% | 49.6% | -1.6% | -9.1% ± 13.5% |
| total:over | 50 | 60.0% | 50.0% | +10.0% | +12.4% ± 13.1% |
| total:under | 50 | 40.0% | 50.0% | -10.0% | -25.8% ± 13.0% |
| win:away | 51 | 35.3% | 41.2% | -5.9% | -28.7% ± 15.9% |
| win:home | 51 | 64.7% | 58.8% | +5.9% | -2.4% ± 11.3% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 99 | 50.5% | 50.0% | +0.5% | -5.4% ± 9.5% |
| total @ 1.60–2.00 | 100 | 50.0% | 50.0% | +0.0% | -6.7% ± 9.4% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 12 | +0.0% | -6.7% |
| not covered | hcp | 88 | +0.0% | -6.3% |
| covered | total | 12 | +0.0% | -6.7% |
| not covered | total | 88 | +0.0% | -6.7% |
| covered | win | 12 | +0.0% | +19.5% |
| not covered | win | 90 | +0.0% | -20.2% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 32 | 53.1% | 52.7% | +0.5% | +2.6% ± 20.6% |
| steady | 134 | 51.5% | 51.5% | -0.0% | -6.1% ± 8.0% |
| drifted 3%+ | 38 | 42.1% | 42.4% | -0.3% | -15.7% ± 17.1% |

