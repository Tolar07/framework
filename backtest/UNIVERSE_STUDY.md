# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

36 games graded (100% of 36 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-07.

## Football — 20 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 15 | 26.7% | 31.2% | -4.6% | -46.7% ± 24.3% |
| 1x2:draw | 15 | 13.3% | 26.9% | -13.6% | -55.0% ± 30.9% |
| 1x2:home | 15 | 60.0% | 41.9% | +18.1% | +14.0% ± 25.3% |
| btts:no | 13 | 61.5% | 50.8% | +10.7% | +11.2% ± 26.5% |
| btts:yes | 13 | 38.5% | 49.2% | -10.7% | -30.7% ± 25.6% |
| dc:12 | 15 | 86.7% | 36.3% | +50.4% | +9.9% ± 11.6% |
| dc:1x | 15 | 73.3% | 34.1% | +39.2% | -8.8% ± 14.8% |
| dc:x2 | 15 | 40.0% | 29.6% | +10.4% | -44.3% ± 18.7% |
| o/u1.5:over | 13 | 69.2% | 69.4% | -0.2% | -6.6% ± 18.3% |
| o/u1.5:under | 13 | 30.8% | 30.6% | +0.2% | +5.2% ± 48.4% |
| o/u2.5:over | 13 | 69.2% | 47.0% | +22.2% | +43.6% ± 29.4% |
| o/u2.5:under | 13 | 30.8% | 53.0% | -22.2% | -40.9% ± 26.5% |
| o/u3.5:over | 13 | 46.2% | 28.3% | +17.9% | +77.3% ± 59.8% |
| o/u3.5:under | 13 | 53.8% | 71.7% | -17.9% | -28.2% ± 19.5% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| not covered | 1x2 | 45 | -0.0% | -29.2% |
| not covered | btts | 26 | +0.0% | -9.8% |
| not covered | dc | 45 | +33.3% | -14.4% |
| not covered | o/u1.5 | 26 | +0.0% | -0.7% |
| not covered | o/u2.5 | 26 | +0.0% | +1.3% |
| not covered | o/u3.5 | 26 | +0.0% | +24.5% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|

## Basketball — 16 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 16 | 56.2% | 50.5% | +5.7% | +4.3% ± 23.8% |
| hcp:home | 16 | 43.8% | 49.5% | -5.7% | -16.6% ± 24.4% |
| total:over | 16 | 37.5% | 50.0% | -12.5% | -28.8% ± 23.7% |
| total:under | 16 | 62.5% | 50.0% | +12.5% | +16.3% ± 23.3% |
| win:away | 16 | 18.8% | 32.7% | -13.9% | -69.4% ± 18.9% |
| win:home | 16 | 81.2% | 67.3% | +13.9% | +3.1% ± 13.5% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 31 | 51.6% | 50.1% | +1.6% | -3.1% ± 17.1% |
| total @ 1.60–2.00 | 32 | 50.0% | 50.0% | +0.0% | -6.3% ± 16.8% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| not covered | hcp | 32 | +0.0% | -6.1% |
| not covered | total | 32 | +0.0% | -6.3% |
| not covered | win | 32 | +0.0% | -33.2% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|

