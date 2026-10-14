# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

2635 games graded (100% of 2635 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-14.

## Football — 2239 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 2221 | 32.0% | 32.0% | -0.0% | -10.4% ± 3.3% |
| 1x2:draw | 2221 | 23.0% | 24.8% | -1.8% | -15.7% ± 3.4% |
| 1x2:home | 2221 | 45.0% | 43.1% | +1.9% | -5.9% ± 2.6% |
| btts:no | 1908 | 45.5% | 46.0% | -0.5% | -8.7% ± 2.4% |
| btts:yes | 1908 | 54.5% | 54.0% | +0.5% | -7.3% ± 2.0% |
| dc:12 | 2136 | 77.1% | 74.3% | +2.8% | -4.3% ± 1.1% |
| dc:1x | 2136 | 67.9% | 67.7% | +0.2% | -8.7% ± 1.5% |
| dc:x2 | 2136 | 55.0% | 57.9% | -2.9% | -14.8% ± 1.8% |
| o/u1.5:over | 1675 | 76.1% | 74.1% | +2.1% | -4.1% ± 1.3% |
| o/u1.5:under | 1675 | 23.9% | 25.9% | -2.1% | -15.1% ± 3.9% |
| o/u2.5:over | 2090 | 55.2% | 53.6% | +1.5% | -4.3% ± 2.0% |
| o/u2.5:under | 2090 | 44.8% | 46.4% | -1.5% | -10.3% ± 2.3% |
| o/u3.5:over | 1924 | 35.5% | 35.8% | -0.4% | -7.2% ± 3.0% |
| o/u3.5:under | 1924 | 64.5% | 64.2% | +0.4% | -5.9% ± 1.7% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 171 | 81.3% | 78.3% | +3.0% | -4.0% ± 3.6% |
| 1x2 @ 1.30–1.60 | 396 | 67.2% | 63.3% | +3.9% | -2.0% ± 3.5% |
| 1x2 @ 1.60–2.00 | 662 | 56.2% | 51.5% | +4.6% | +0.2% ± 3.5% |
| 1x2 @ 2.00–3.00 | 1701 | 38.7% | 37.6% | +1.1% | -5.5% ± 2.9% |
| 1x2 @ 3.00–5.00 | 2954 | 23.3% | 25.4% | -2.1% | -16.2% ± 2.8% |
| 1x2 @ 5.00–1000.00 | 779 | 12.3% | 13.5% | -1.2% | -16.0% ± 8.6% |
| btts @ 1.00–1.30 | 38 | 63.2% | 73.3% | -10.1% | -21.6% ± 9.9% |
| btts @ 1.30–1.60 | 809 | 59.2% | 61.4% | -2.2% | -12.0% ± 2.6% |
| btts @ 1.60–2.00 | 1743 | 51.3% | 51.3% | +0.0% | -8.8% ± 2.1% |
| btts @ 2.00–3.00 | 1170 | 41.7% | 40.5% | +1.2% | -5.7% ± 3.3% |
| btts @ 3.00–5.00 | 56 | 41.1% | 27.9% | +13.2% | +35.1% ± 22.0% |
| dc @ 1.00–1.30 | 2910 | 80.6% | 77.2% | +3.4% | -3.6% ± 0.9% |
| dc @ 1.30–1.60 | 2096 | 65.9% | 66.0% | -0.2% | -7.8% ± 1.5% |
| dc @ 1.60–2.00 | 786 | 46.6% | 52.7% | -6.2% | -18.6% ± 3.1% |
| dc @ 2.00–3.00 | 474 | 33.5% | 40.2% | -6.7% | -22.7% ± 5.1% |
| dc @ 3.00–5.00 | 126 | 15.9% | 26.6% | -10.7% | -43.5% ± 11.8% |
| o/u1.5 @ 1.00–1.30 | 1074 | 80.4% | 78.3% | +2.1% | -4.0% ± 1.5% |
| o/u1.5 @ 1.30–1.60 | 566 | 69.1% | 67.2% | +1.8% | -4.5% ± 2.7% |
| o/u1.5 @ 1.60–2.00 | 40 | 65.0% | 54.8% | +10.2% | +11.1% ± 13.2% |
| o/u1.5 @ 2.00–3.00 | 364 | 34.6% | 35.7% | -1.1% | -8.7% ± 6.6% |
| o/u1.5 @ 3.00–5.00 | 1042 | 22.8% | 25.0% | -2.2% | -14.0% ± 5.0% |
| o/u1.5 @ 5.00–1000.00 | 264 | 11.7% | 15.8% | -4.0% | -30.6% ± 12.0% |
| o/u2.5 @ 1.00–1.30 | 81 | 81.5% | 75.7% | +5.8% | +0.6% ± 5.4% |
| o/u2.5 @ 1.30–1.60 | 838 | 62.8% | 63.1% | -0.4% | -7.6% ± 2.5% |
| o/u2.5 @ 1.60–2.00 | 1673 | 53.2% | 52.3% | +0.9% | -5.6% ± 2.2% |
| o/u2.5 @ 2.00–3.00 | 1421 | 40.0% | 40.8% | -0.8% | -8.6% ± 3.0% |
| o/u2.5 @ 3.00–5.00 | 159 | 25.2% | 27.8% | -2.6% | -12.9% ± 12.1% |
| o/u3.5 @ 1.00–1.30 | 495 | 73.3% | 75.7% | -2.4% | -10.1% ± 2.4% |
| o/u3.5 @ 1.30–1.60 | 971 | 65.2% | 65.1% | +0.1% | -6.7% ± 2.2% |
| o/u3.5 @ 1.60–2.00 | 620 | 55.0% | 52.9% | +2.1% | -3.4% ± 3.5% |
| o/u3.5 @ 2.00–3.00 | 1037 | 37.8% | 38.7% | -0.9% | -8.5% ± 3.7% |
| o/u3.5 @ 3.00–5.00 | 690 | 27.8% | 26.5% | +1.3% | -1.5% ± 6.1% |
| o/u3.5 @ 5.00–1000.00 | 35 | 8.6% | 16.3% | -7.8% | -52.0% ± 26.9% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Sweden · Division 2 — dc:1x | 37 | 59.5% | 71.4% | -11.9% | -22.6% ± 11.0% |
| Spain · Segunda Federacion — 1x2:away | 34 | 11.8% | 27.6% | -15.9% | -62.2% ± 18.4% |
| Sweden · Division 2 — 1x2:draw | 37 | 8.1% | 22.3% | -14.2% | -70.0% ± 16.8% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 687 | -0.0% | -8.5% |
| not covered | 1x2 | 5976 | -0.0% | -10.9% |
| covered | btts | 458 | +0.0% | -3.4% |
| not covered | btts | 3358 | +0.0% | -8.7% |
| covered | dc | 687 | +0.0% | -7.6% |
| not covered | dc | 5721 | -0.0% | -9.4% |
| covered | o/u1.5 | 452 | +0.0% | -5.0% |
| not covered | o/u1.5 | 2898 | +0.0% | -10.3% |
| covered | o/u2.5 | 458 | +0.0% | -4.8% |
| not covered | o/u2.5 | 3722 | +0.0% | -7.6% |
| covered | o/u3.5 | 458 | +0.0% | -5.2% |
| not covered | o/u3.5 | 3390 | +0.0% | -6.8% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 4502 | 48.6% | 47.9% | +0.7% | +1.2% ± 1.9% |
| steady | 15115 | 54.3% | 53.9% | +0.4% | -8.1% ± 0.8% |
| drifted 3%+ | 5854 | 38.5% | 40.0% | -1.5% | -19.4% ± 1.6% |

## Basketball — 396 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 394 | 51.5% | 50.2% | +1.4% | -4.6% ± 4.7% |
| hcp:home | 394 | 48.5% | 49.8% | -1.4% | -9.6% ± 4.7% |
| total:over | 394 | 51.8% | 50.1% | +1.7% | -4.0% ± 4.7% |
| total:under | 394 | 48.2% | 49.9% | -1.7% | -10.4% ± 4.7% |
| win:away | 394 | 42.9% | 43.4% | -0.5% | -9.5% ± 6.5% |
| win:home | 394 | 57.1% | 56.6% | +0.5% | -7.1% ± 5.1% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 785 | 50.1% | 50.0% | +0.1% | -7.0% ± 3.3% |
| total @ 1.60–2.00 | 787 | 50.1% | 50.0% | +0.1% | -7.1% ± 3.3% |
| win @ 1.00–1.30 | 144 | 82.6% | 82.2% | +0.4% | -6.5% ± 3.6% |
| win @ 1.30–1.60 | 145 | 64.1% | 65.4% | -1.3% | -8.5% ± 5.7% |
| win @ 1.60–2.00 | 133 | 50.4% | 53.4% | -3.0% | -11.3% ± 7.7% |
| win @ 2.00–3.00 | 183 | 43.7% | 39.7% | +4.1% | +2.9% ± 8.8% |
| win @ 3.00–5.00 | 105 | 27.6% | 25.9% | +1.8% | +2.5% ± 16.5% |
| win @ 5.00–1000.00 | 78 | 7.7% | 12.9% | -5.2% | -46.9% ± 21.5% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 46 | +0.0% | -7.0% |
| not covered | hcp | 742 | +0.0% | -7.1% |
| covered | total | 46 | +0.0% | -6.8% |
| not covered | total | 742 | +0.0% | -7.2% |
| covered | win | 46 | -0.0% | -3.0% |
| not covered | win | 742 | +0.0% | -8.6% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 352 | 48.0% | 49.3% | -1.3% | +0.9% ± 6.7% |
| steady | 1412 | 51.4% | 51.6% | -0.2% | -7.1% ± 2.6% |
| drifted 3%+ | 378 | 46.6% | 44.7% | +1.8% | -14.1% ± 5.1% |

