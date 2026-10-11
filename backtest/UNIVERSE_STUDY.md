# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

1491 games graded (100% of 1491 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-11.

## Football — 1246 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 1235 | 32.5% | 32.4% | +0.1% | -8.6% ± 4.6% |
| 1x2:draw | 1235 | 23.0% | 24.6% | -1.6% | -15.0% ± 4.6% |
| 1x2:home | 1235 | 44.5% | 43.1% | +1.5% | -7.0% ± 3.5% |
| btts:no | 1096 | 46.8% | 45.3% | +1.5% | -5.1% ± 3.2% |
| btts:yes | 1096 | 53.2% | 54.7% | -1.5% | -11.3% ± 2.6% |
| dc:12 | 1222 | 76.8% | 37.3% | +39.6% | -4.8% ± 1.5% |
| dc:1x | 1222 | 67.6% | 33.8% | +33.8% | -8.8% ± 1.9% |
| dc:x2 | 1222 | 55.6% | 29.0% | +26.6% | -13.6% ± 2.4% |
| o/u1.5:over | 941 | 74.8% | 74.5% | +0.3% | -6.4% ± 1.8% |
| o/u1.5:under | 941 | 25.2% | 25.5% | -0.3% | -9.5% ± 5.4% |
| o/u2.5:over | 1159 | 55.5% | 54.6% | +0.8% | -5.5% ± 2.6% |
| o/u2.5:under | 1159 | 44.5% | 45.4% | -0.8% | -8.8% ± 3.1% |
| o/u3.5:over | 1111 | 34.8% | 36.6% | -1.8% | -10.9% ± 3.9% |
| o/u3.5:under | 1111 | 65.2% | 63.4% | +1.8% | -4.0% ± 2.2% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 94 | 80.9% | 78.1% | +2.7% | -4.4% ± 4.9% |
| 1x2 @ 1.30–1.60 | 221 | 64.7% | 63.4% | +1.3% | -5.9% ± 4.7% |
| 1x2 @ 1.60–2.00 | 372 | 57.0% | 51.5% | +5.5% | +1.7% ± 4.6% |
| 1x2 @ 2.00–3.00 | 936 | 39.1% | 37.7% | +1.4% | -4.8% ± 3.9% |
| 1x2 @ 3.00–5.00 | 1657 | 22.9% | 25.3% | -2.4% | -17.1% ± 3.8% |
| 1x2 @ 5.00–1000.00 | 425 | 13.6% | 13.5% | +0.1% | -9.2% ± 12.0% |
| btts @ 1.30–1.60 | 488 | 61.3% | 61.5% | -0.2% | -9.1% ± 3.3% |
| btts @ 1.60–2.00 | 942 | 51.0% | 51.3% | -0.4% | -9.5% ± 2.9% |
| btts @ 2.00–3.00 | 697 | 40.7% | 40.4% | +0.3% | -7.7% ± 4.3% |
| btts @ 3.00–5.00 | 37 | 43.2% | 28.2% | +15.0% | +39.9% ± 26.8% |
| dc @ 1.00–1.30 | 1687 | 80.1% | 38.6% | +41.6% | -4.0% ± 1.2% |
| dc @ 1.30–1.60 | 1178 | 65.6% | 33.0% | +32.7% | -8.1% ± 1.9% |
| dc @ 1.60–2.00 | 448 | 46.7% | 26.4% | +20.3% | -18.9% ± 4.1% |
| dc @ 2.00–3.00 | 275 | 35.6% | 20.1% | +15.6% | -17.5% ± 6.8% |
| dc @ 3.00–5.00 | 69 | 17.4% | 13.1% | +4.3% | -38.8% ± 16.4% |
| o/u1.5 @ 1.00–1.30 | 622 | 79.3% | 78.5% | +0.7% | -5.6% ± 1.9% |
| o/u1.5 @ 1.30–1.60 | 303 | 67.3% | 67.3% | +0.1% | -6.9% ± 3.7% |
| o/u1.5 @ 2.00–3.00 | 186 | 37.1% | 35.7% | +1.4% | -2.6% ± 9.4% |
| o/u1.5 @ 3.00–5.00 | 598 | 25.3% | 24.8% | +0.5% | -3.2% ± 6.9% |
| o/u1.5 @ 5.00–1000.00 | 154 | 9.1% | 15.6% | -6.5% | -44.4% ± 14.6% |
| o/u2.5 @ 1.00–1.30 | 52 | 80.8% | 75.4% | +5.4% | +0.1% ± 6.9% |
| o/u2.5 @ 1.30–1.60 | 484 | 61.8% | 63.3% | -1.5% | -9.4% ± 3.3% |
| o/u2.5 @ 1.60–2.00 | 876 | 53.3% | 52.4% | +0.9% | -5.6% ± 3.0% |
| o/u2.5 @ 2.00–3.00 | 808 | 40.5% | 40.6% | -0.1% | -7.1% ± 4.0% |
| o/u2.5 @ 3.00–5.00 | 93 | 25.8% | 27.8% | -1.9% | -10.0% ± 16.1% |
| o/u3.5 @ 1.00–1.30 | 252 | 72.6% | 75.6% | -3.0% | -10.7% ± 3.5% |
| o/u3.5 @ 1.30–1.60 | 561 | 67.7% | 64.9% | +2.9% | -2.9% ± 2.8% |
| o/u3.5 @ 1.60–2.00 | 403 | 56.3% | 52.9% | +3.4% | -1.2% ± 4.4% |
| o/u3.5 @ 2.00–3.00 | 631 | 35.8% | 38.9% | -3.1% | -13.9% ± 4.6% |
| o/u3.5 @ 3.00–5.00 | 357 | 26.1% | 26.6% | -0.6% | -6.4% ± 8.4% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 408 | +0.0% | -9.4% |
| not covered | 1x2 | 3297 | -0.0% | -10.3% |
| covered | btts | 272 | +0.0% | -3.2% |
| not covered | btts | 1920 | +0.0% | -8.9% |
| covered | dc | 408 | +33.3% | -7.5% |
| not covered | dc | 3258 | +33.3% | -9.2% |
| covered | o/u1.5 | 266 | +0.0% | -1.8% |
| not covered | o/u1.5 | 1616 | +0.0% | -9.0% |
| covered | o/u2.5 | 272 | +0.0% | -4.3% |
| not covered | o/u2.5 | 2046 | +0.0% | -7.5% |
| covered | o/u3.5 | 272 | +0.0% | -10.5% |
| not covered | o/u3.5 | 1950 | +0.0% | -7.0% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 2552 | 47.1% | 41.6% | +5.6% | -3.6% ± 2.4% |
| steady | 8836 | 54.4% | 44.3% | +10.1% | -7.8% ± 1.1% |
| drifted 3%+ | 3282 | 39.9% | 35.5% | +4.3% | -15.9% ± 2.1% |

## Basketball — 245 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 244 | 53.7% | 50.2% | +3.5% | -0.7% ± 5.9% |
| hcp:home | 244 | 46.3% | 49.8% | -3.5% | -13.5% ± 6.0% |
| total:over | 243 | 53.5% | 50.1% | +3.4% | -0.8% ± 5.9% |
| total:under | 243 | 46.5% | 49.9% | -3.4% | -13.7% ± 6.0% |
| win:away | 244 | 44.7% | 42.7% | +1.9% | -4.9% ± 8.3% |
| win:home | 244 | 55.3% | 57.3% | -1.9% | -13.3% ± 5.6% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 487 | 50.1% | 50.0% | +0.1% | -6.9% ± 4.2% |
| total @ 1.60–2.00 | 486 | 50.0% | 50.0% | +0.0% | -7.2% ± 4.2% |
| win @ 1.00–1.30 | 89 | 84.3% | 82.4% | +1.9% | -4.9% ± 4.5% |
| win @ 1.30–1.60 | 87 | 59.8% | 64.8% | -5.0% | -14.3% ± 7.6% |
| win @ 1.60–2.00 | 88 | 50.0% | 53.4% | -3.4% | -11.5% ± 9.5% |
| win @ 2.00–3.00 | 114 | 46.5% | 39.8% | +6.7% | +8.7% ± 11.1% |
| win @ 3.00–5.00 | 62 | 25.8% | 25.6% | +0.2% | -5.5% ± 20.8% |
| win @ 5.00–1000.00 | 48 | 8.3% | 12.6% | -4.3% | -50.1% ± 24.2% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 24 | +0.0% | -6.9% |
| not covered | hcp | 464 | +0.0% | -7.1% |
| covered | total | 24 | +0.0% | -6.7% |
| not covered | total | 462 | +0.0% | -7.2% |
| covered | win | 24 | -0.0% | +7.2% |
| not covered | win | 464 | +0.0% | -9.9% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 216 | 49.5% | 50.1% | -0.6% | +3.3% ± 8.3% |
| steady | 859 | 51.5% | 51.5% | -0.1% | -7.0% ± 3.2% |
| drifted 3%+ | 235 | 45.1% | 44.2% | +0.9% | -16.8% ± 6.3% |

