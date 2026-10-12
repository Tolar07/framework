# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

2247 games graded (100% of 2247 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-12.

## Football — 1917 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 1901 | 31.9% | 32.3% | -0.3% | -11.1% ± 3.6% |
| 1x2:draw | 1901 | 23.7% | 24.9% | -1.3% | -14.5% ± 3.6% |
| 1x2:home | 1901 | 44.4% | 42.8% | +1.6% | -7.0% ± 2.8% |
| btts:no | 1611 | 45.8% | 45.8% | -0.0% | -7.9% ± 2.6% |
| btts:yes | 1611 | 54.2% | 54.2% | +0.0% | -8.3% ± 2.1% |
| dc:12 | 1821 | 76.3% | 37.1% | +39.2% | -5.2% ± 1.2% |
| dc:1x | 1821 | 68.0% | 33.8% | +34.2% | -8.5% ± 1.6% |
| dc:x2 | 1821 | 55.7% | 29.1% | +26.6% | -13.9% ± 1.9% |
| o/u1.5:over | 1411 | 75.5% | 74.0% | +1.4% | -4.9% ± 1.5% |
| o/u1.5:under | 1411 | 24.5% | 26.0% | -1.4% | -12.9% ± 4.3% |
| o/u2.5:over | 1788 | 54.0% | 53.5% | +0.4% | -6.5% ± 2.1% |
| o/u2.5:under | 1788 | 46.0% | 46.5% | -0.4% | -8.4% ± 2.5% |
| o/u3.5:over | 1633 | 33.9% | 35.8% | -1.9% | -12.0% ± 3.2% |
| o/u3.5:under | 1633 | 66.1% | 64.2% | +1.9% | -4.0% ± 1.8% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 130 | 82.3% | 77.6% | +4.7% | -2.3% ± 4.0% |
| 1x2 @ 1.30–1.60 | 337 | 66.8% | 63.1% | +3.6% | -2.6% ± 3.8% |
| 1x2 @ 1.60–2.00 | 576 | 55.6% | 51.5% | +4.0% | -1.1% ± 3.7% |
| 1x2 @ 2.00–3.00 | 1473 | 38.7% | 37.6% | +1.1% | -5.4% ± 3.1% |
| 1x2 @ 3.00–5.00 | 2561 | 23.5% | 25.4% | -1.9% | -15.6% ± 3.0% |
| 1x2 @ 5.00–1000.00 | 626 | 12.3% | 13.8% | -1.5% | -19.5% ± 9.2% |
| btts @ 1.00–1.30 | 33 | 63.6% | 73.0% | -9.3% | -20.7% ± 10.6% |
| btts @ 1.30–1.60 | 669 | 59.2% | 61.3% | -2.2% | -12.1% ± 2.8% |
| btts @ 1.60–2.00 | 1494 | 51.1% | 51.3% | -0.2% | -9.2% ± 2.3% |
| btts @ 2.00–3.00 | 982 | 42.2% | 40.6% | +1.6% | -4.9% ± 3.6% |
| btts @ 3.00–5.00 | 44 | 38.6% | 27.9% | +10.8% | +26.8% ± 24.5% |
| dc @ 1.00–1.30 | 2476 | 80.2% | 38.5% | +41.7% | -3.9% ± 1.0% |
| dc @ 1.30–1.60 | 1808 | 65.7% | 33.0% | +32.7% | -8.0% ± 1.6% |
| dc @ 1.60–2.00 | 670 | 47.5% | 26.3% | +21.1% | -17.1% ± 3.4% |
| dc @ 2.00–3.00 | 404 | 33.9% | 20.2% | +13.7% | -22.1% ± 5.5% |
| dc @ 3.00–5.00 | 95 | 14.7% | 13.3% | +1.5% | -48.3% ± 13.0% |
| o/u1.5 @ 1.00–1.30 | 902 | 79.7% | 78.2% | +1.6% | -4.6% ± 1.6% |
| o/u1.5 @ 1.30–1.60 | 481 | 68.4% | 67.3% | +1.1% | -5.7% ± 2.9% |
| o/u1.5 @ 1.60–2.00 | 32 | 65.6% | 54.7% | +10.9% | +12.2% ± 14.7% |
| o/u1.5 @ 2.00–3.00 | 305 | 35.4% | 35.5% | -0.1% | -6.4% ± 7.3% |
| o/u1.5 @ 3.00–5.00 | 889 | 23.5% | 25.0% | -1.5% | -11.1% ± 5.4% |
| o/u1.5 @ 5.00–1000.00 | 213 | 11.7% | 15.8% | -4.1% | -31.3% ± 13.2% |
| o/u2.5 @ 1.00–1.30 | 63 | 84.1% | 75.3% | +8.9% | +4.3% ± 5.8% |
| o/u2.5 @ 1.30–1.60 | 700 | 62.7% | 63.1% | -0.4% | -7.7% ± 2.7% |
| o/u2.5 @ 1.60–2.00 | 1470 | 52.8% | 52.3% | +0.5% | -6.2% ± 2.3% |
| o/u2.5 @ 2.00–3.00 | 1213 | 40.4% | 40.8% | -0.4% | -7.9% ± 3.2% |
| o/u2.5 @ 3.00–5.00 | 125 | 24.0% | 27.9% | -3.9% | -18.2% ± 13.2% |
| o/u3.5 @ 1.00–1.30 | 420 | 75.0% | 75.5% | -0.5% | -7.9% ± 2.6% |
| o/u3.5 @ 1.30–1.60 | 821 | 67.6% | 65.0% | +2.6% | -3.2% ± 2.4% |
| o/u3.5 @ 1.60–2.00 | 534 | 55.8% | 52.9% | +2.9% | -2.1% ± 3.8% |
| o/u3.5 @ 2.00–3.00 | 882 | 35.3% | 38.6% | -3.4% | -14.7% ± 3.9% |
| o/u3.5 @ 3.00–5.00 | 582 | 26.1% | 26.5% | -0.4% | -7.7% ± 6.5% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Spain · Segunda Federacion — 1x2:away | 34 | 11.8% | 27.6% | -15.9% | -62.2% ± 18.4% |
| Sweden · Division 2 — 1x2:draw | 36 | 8.3% | 22.3% | -14.0% | -69.2% ± 17.3% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 582 | +0.0% | -10.7% |
| not covered | 1x2 | 5121 | +0.0% | -10.9% |
| covered | btts | 388 | +0.0% | -3.0% |
| not covered | btts | 2834 | +0.0% | -8.8% |
| covered | dc | 582 | +33.3% | -8.1% |
| not covered | dc | 4881 | +33.3% | -9.3% |
| covered | o/u1.5 | 382 | +0.0% | -3.3% |
| not covered | o/u1.5 | 2440 | +0.0% | -9.8% |
| covered | o/u2.5 | 388 | +0.0% | -4.4% |
| not covered | o/u2.5 | 3188 | +0.0% | -7.8% |
| covered | o/u3.5 | 388 | +0.0% | -7.8% |
| not covered | o/u3.5 | 2878 | +0.0% | -8.0% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 3779 | 47.8% | 41.4% | +6.4% | -1.1% ± 2.0% |
| steady | 13243 | 54.0% | 44.2% | +9.9% | -8.2% ± 0.9% |
| drifted 3%+ | 4861 | 39.3% | 35.5% | +3.8% | -18.2% ± 1.7% |

## Basketball — 330 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 328 | 51.5% | 50.2% | +1.4% | -4.6% ± 5.1% |
| hcp:home | 328 | 48.5% | 49.8% | -1.4% | -9.5% ± 5.2% |
| total:over | 328 | 52.7% | 50.1% | +2.7% | -2.2% ± 5.1% |
| total:under | 328 | 47.3% | 49.9% | -2.7% | -12.3% ± 5.1% |
| win:away | 328 | 43.9% | 43.0% | +0.9% | -7.2% ± 7.2% |
| win:home | 328 | 56.1% | 57.0% | -0.9% | -10.4% ± 5.5% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 654 | 50.0% | 50.0% | -0.0% | -7.1% ± 3.6% |
| total @ 1.60–2.00 | 655 | 50.1% | 50.0% | +0.1% | -7.1% ± 3.6% |
| win @ 1.00–1.30 | 124 | 83.9% | 82.5% | +1.3% | -5.3% ± 3.8% |
| win @ 1.30–1.60 | 111 | 63.1% | 65.1% | -2.0% | -10.0% ± 6.6% |
| win @ 1.60–2.00 | 119 | 49.6% | 53.2% | -3.7% | -12.4% ± 8.2% |
| win @ 2.00–3.00 | 149 | 45.6% | 40.1% | +5.5% | +5.7% ± 9.6% |
| win @ 3.00–5.00 | 84 | 25.0% | 25.7% | -0.7% | -7.6% ± 17.8% |
| win @ 5.00–1000.00 | 69 | 8.7% | 12.7% | -4.0% | -39.9% ± 24.1% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 28 | +0.0% | -6.7% |
| not covered | hcp | 628 | +0.0% | -7.1% |
| covered | total | 28 | +0.0% | -6.7% |
| not covered | total | 628 | +0.0% | -7.3% |
| covered | win | 28 | -0.0% | +4.1% |
| not covered | win | 628 | +0.0% | -9.4% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 283 | 49.1% | 49.5% | -0.4% | +2.9% ± 7.5% |
| steady | 1181 | 51.2% | 51.6% | -0.4% | -7.3% ± 2.8% |
| drifted 3%+ | 314 | 46.2% | 44.3% | +1.9% | -15.5% ± 5.4% |

