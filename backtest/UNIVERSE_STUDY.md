# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

47 games graded (100% of 47 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-08.

## Football — 25 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 20 | 25.0% | 30.7% | -5.7% | -48.3% ± 21.0% |
| 1x2:draw | 20 | 10.0% | 25.6% | -15.6% | -66.2% ± 23.4% |
| 1x2:home | 20 | 65.0% | 43.7% | +21.3% | +34.5% ± 29.3% |
| btts:no | 17 | 64.7% | 49.9% | +14.8% | +17.9% ± 22.6% |
| btts:yes | 17 | 35.3% | 50.1% | -14.8% | -37.9% ± 21.3% |
| dc:12 | 19 | 89.5% | 36.6% | +52.9% | +12.5% ± 9.2% |
| dc:1x | 19 | 73.7% | 34.0% | +39.7% | -4.7% ± 14.3% |
| dc:x2 | 19 | 36.8% | 29.4% | +7.4% | -48.7% ± 16.2% |
| o/u1.5:over | 16 | 68.8% | 70.2% | -1.5% | -8.3% ± 16.2% |
| o/u1.5:under | 16 | 31.2% | 29.8% | +1.5% | +7.4% ± 43.2% |
| o/u2.5:over | 17 | 58.8% | 49.0% | +9.8% | +19.8% ± 26.2% |
| o/u2.5:under | 17 | 41.2% | 51.0% | -9.8% | -16.0% ± 26.3% |
| o/u3.5:over | 17 | 41.2% | 30.0% | +11.2% | +51.2% ± 48.8% |
| o/u3.5:under | 17 | 58.8% | 70.0% | -11.2% | -18.9% ± 17.4% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| not covered | 1x2 | 60 | +0.0% | -26.7% |
| not covered | btts | 34 | +0.0% | -10.0% |
| not covered | dc | 57 | +33.3% | -13.6% |
| not covered | o/u1.5 | 32 | +0.0% | -0.5% |
| not covered | o/u2.5 | 34 | +0.0% | +1.9% |
| not covered | o/u3.5 | 34 | +0.0% | +16.1% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 9 | 55.6% | 45.4% | +10.1% | -4.3% ± 33.5% |
| steady | 40 | 50.0% | 43.2% | +6.8% | -7.2% ± 18.6% |
| drifted 3%+ | 8 | 37.5% | 32.9% | +4.6% | -24.1% ± 38.2% |

## Basketball — 22 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 22 | 59.1% | 50.4% | +8.7% | +9.9% ± 20.0% |
| hcp:home | 22 | 40.9% | 49.6% | -8.7% | -22.0% ± 20.5% |
| total:over | 22 | 54.5% | 50.1% | +4.4% | +2.7% ± 20.5% |
| total:under | 22 | 45.5% | 49.9% | -4.4% | -15.5% ± 20.2% |
| win:away | 22 | 27.3% | 35.1% | -7.8% | -40.1% ± 26.0% |
| win:home | 22 | 72.7% | 64.9% | +7.8% | -1.7% ± 14.3% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 43 | 51.2% | 50.0% | +1.1% | -3.9% ± 14.5% |
| total @ 1.60–2.00 | 44 | 50.0% | 50.0% | +0.0% | -6.4% ± 14.3% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 8 | +0.0% | -7.1% |
| not covered | hcp | 36 | +0.0% | -5.8% |
| covered | total | 8 | +0.0% | -7.1% |
| not covered | total | 36 | +0.0% | -6.2% |
| covered | win | 8 | +0.0% | +22.8% |
| not covered | win | 36 | +0.0% | -30.6% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 2 | 100.0% | 35.3% | +64.7% | +255.0% ± 165.0% |
| steady | 31 | 51.6% | 52.0% | -0.4% | -5.5% ± 16.9% |
| drifted 3%+ | 3 | 0.0% | 39.0% | -39.0% | -100.0% ± 0.0% |

