# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

525 games graded (100% of 525 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-10.

## Football — 402 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 395 | 32.7% | 33.9% | -1.3% | -8.8% ± 9.2% |
| 1x2:draw | 395 | 20.8% | 24.4% | -3.6% | -24.1% ± 7.7% |
| 1x2:home | 395 | 46.6% | 41.7% | +4.9% | -1.9% ± 6.1% |
| btts:no | 354 | 51.7% | 47.0% | +4.7% | +2.0% ± 5.5% |
| btts:yes | 354 | 48.3% | 53.0% | -4.7% | -17.1% ± 4.7% |
| dc:12 | 391 | 79.0% | 37.4% | +41.7% | -2.4% ± 2.6% |
| dc:1x | 391 | 67.8% | 33.1% | +34.7% | -7.9% ± 3.5% |
| dc:x2 | 391 | 53.2% | 29.5% | +23.7% | -19.1% ± 4.2% |
| o/u1.5:over | 317 | 75.1% | 73.7% | +1.3% | -5.1% ± 3.1% |
| o/u1.5:under | 317 | 24.9% | 26.3% | -1.3% | -12.8% ± 9.0% |
| o/u2.5:over | 375 | 54.9% | 53.9% | +1.0% | -4.5% ± 4.7% |
| o/u2.5:under | 375 | 45.1% | 46.1% | -1.0% | -7.7% ± 5.6% |
| o/u3.5:over | 351 | 35.6% | 35.7% | -0.0% | -3.9% ± 7.4% |
| o/u3.5:under | 351 | 64.4% | 64.3% | +0.0% | -5.9% ± 3.9% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 41 | 82.9% | 78.2% | +4.7% | -2.0% ± 7.1% |
| 1x2 @ 1.30–1.60 | 79 | 69.6% | 64.1% | +5.6% | -0.2% ± 7.5% |
| 1x2 @ 1.60–2.00 | 118 | 58.5% | 51.4% | +7.1% | +4.7% ± 8.2% |
| 1x2 @ 2.00–3.00 | 273 | 37.7% | 37.3% | +0.5% | -6.7% ± 7.3% |
| 1x2 @ 3.00–5.00 | 498 | 22.1% | 25.4% | -3.3% | -21.6% ± 6.7% |
| 1x2 @ 5.00–1000.00 | 176 | 13.6% | 13.4% | +0.3% | -9.0% ± 19.6% |
| btts @ 1.30–1.60 | 156 | 59.0% | 61.3% | -2.4% | -11.8% ± 5.9% |
| btts @ 1.60–2.00 | 316 | 50.9% | 51.2% | -0.3% | -9.1% ± 5.0% |
| btts @ 2.00–3.00 | 223 | 41.7% | 40.6% | +1.1% | -5.0% ± 7.6% |
| dc @ 1.00–1.30 | 545 | 82.2% | 38.9% | +43.3% | -2.5% ± 2.0% |
| dc @ 1.30–1.60 | 368 | 66.3% | 33.0% | +33.3% | -6.9% ± 3.5% |
| dc @ 1.60–2.00 | 128 | 41.4% | 26.2% | +15.2% | -27.3% ± 7.7% |
| dc @ 2.00–3.00 | 101 | 34.7% | 19.7% | +15.0% | -17.7% ± 11.4% |
| o/u1.5 @ 1.00–1.30 | 193 | 79.8% | 78.6% | +1.1% | -5.2% ± 3.5% |
| o/u1.5 @ 1.30–1.60 | 114 | 69.3% | 67.0% | +2.3% | -3.9% ± 6.0% |
| o/u1.5 @ 2.00–3.00 | 75 | 33.3% | 36.4% | -3.1% | -15.9% ± 13.9% |
| o/u1.5 @ 3.00–5.00 | 191 | 25.1% | 25.0% | +0.1% | -5.7% ± 12.0% |
| o/u1.5 @ 5.00–1000.00 | 50 | 10.0% | 15.2% | -5.2% | -37.6% ± 27.3% |
| o/u2.5 @ 1.30–1.60 | 162 | 63.0% | 63.7% | -0.8% | -8.3% ± 5.6% |
| o/u2.5 @ 1.60–2.00 | 280 | 52.1% | 52.3% | -0.1% | -7.3% ± 5.3% |
| o/u2.5 @ 2.00–3.00 | 257 | 41.6% | 40.3% | +1.3% | -3.8% ± 7.2% |
| o/u2.5 @ 3.00–5.00 | 33 | 30.3% | 28.2% | +2.1% | +10.3% ± 30.2% |
| o/u3.5 @ 1.00–1.30 | 98 | 71.4% | 76.0% | -4.5% | -12.4% ± 5.6% |
| o/u3.5 @ 1.30–1.60 | 165 | 63.6% | 65.1% | -1.4% | -9.1% ± 5.4% |
| o/u3.5 @ 1.60–2.00 | 131 | 53.4% | 52.0% | +1.4% | -4.5% ± 7.9% |
| o/u3.5 @ 2.00–3.00 | 175 | 38.3% | 38.4% | -0.1% | -7.1% ± 9.0% |
| o/u3.5 @ 3.00–5.00 | 125 | 30.4% | 26.1% | +4.3% | +10.8% ± 15.2% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 72 | -0.0% | -8.2% |
| not covered | 1x2 | 1113 | +0.0% | -11.8% |
| covered | btts | 48 | +0.0% | +1.2% |
| not covered | btts | 660 | +0.0% | -8.2% |
| covered | dc | 72 | +33.3% | -7.3% |
| not covered | dc | 1101 | +33.3% | -10.0% |
| covered | o/u1.5 | 48 | +0.0% | +16.3% |
| not covered | o/u1.5 | 586 | +0.0% | -11.0% |
| covered | o/u2.5 | 48 | +0.0% | +4.7% |
| not covered | o/u2.5 | 702 | +0.0% | -6.9% |
| covered | o/u3.5 | 48 | +0.0% | -5.4% |
| not covered | o/u3.5 | 654 | +0.0% | -4.8% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 862 | 46.4% | 41.5% | +4.9% | -4.4% ± 4.1% |
| steady | 2728 | 54.7% | 44.5% | +10.3% | -7.8% ± 1.9% |
| drifted 3%+ | 1034 | 39.9% | 35.7% | +4.3% | -16.1% ± 3.9% |

## Basketball — 123 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 122 | 50.8% | 50.3% | +0.5% | -6.1% ± 8.4% |
| hcp:home | 122 | 49.2% | 49.7% | -0.5% | -7.8% ± 8.5% |
| total:over | 122 | 52.5% | 50.0% | +2.4% | -2.4% ± 8.5% |
| total:under | 122 | 47.5% | 50.0% | -2.4% | -12.0% ± 8.4% |
| win:away | 123 | 40.7% | 43.0% | -2.4% | -18.2% ± 10.4% |
| win:home | 123 | 59.3% | 57.0% | +2.4% | -6.8% ± 7.8% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 243 | 50.2% | 50.0% | +0.2% | -6.5% ± 6.0% |
| total @ 1.60–2.00 | 244 | 50.0% | 50.0% | +0.0% | -7.2% ± 6.0% |
| win @ 1.00–1.30 | 42 | 92.9% | 82.0% | +10.9% | +5.6% ± 4.7% |
| win @ 1.30–1.60 | 44 | 54.5% | 64.8% | -10.3% | -21.2% ± 11.0% |
| win @ 1.60–2.00 | 46 | 56.5% | 53.6% | +3.0% | -0.5% ± 13.1% |
| win @ 2.00–3.00 | 61 | 44.3% | 40.3% | +4.0% | +4.9% ± 15.4% |
| win @ 3.00–5.00 | 32 | 18.8% | 25.2% | -6.4% | -34.8% ± 24.8% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 16 | +0.0% | -7.2% |
| not covered | hcp | 228 | +0.0% | -6.9% |
| covered | total | 16 | +0.0% | -6.9% |
| not covered | total | 228 | +0.0% | -7.2% |
| covered | win | 16 | +0.0% | +14.8% |
| not covered | win | 230 | +0.0% | -14.4% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 111 | 46.8% | 50.6% | -3.7% | -7.6% ± 10.5% |
| steady | 401 | 51.4% | 51.3% | +0.1% | -6.7% ± 4.7% |
| drifted 3%+ | 112 | 48.2% | 45.0% | +3.3% | -13.4% ± 8.9% |

