# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

2507 games graded (100% of 2507 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-13.

## Football — 2134 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 2116 | 32.1% | 32.1% | +0.1% | -10.0% ± 3.4% |
| 1x2:draw | 2116 | 22.9% | 24.9% | -2.0% | -16.5% ± 3.5% |
| 1x2:home | 2116 | 44.9% | 43.0% | +1.9% | -5.9% ± 2.7% |
| btts:no | 1805 | 45.9% | 46.1% | -0.2% | -8.3% ± 2.4% |
| btts:yes | 1805 | 54.1% | 53.9% | +0.2% | -7.9% ± 2.0% |
| dc:12 | 2032 | 77.1% | 74.2% | +2.9% | -4.2% ± 1.2% |
| dc:1x | 2032 | 67.8% | 67.7% | +0.1% | -8.9% ± 1.5% |
| dc:x2 | 2032 | 55.1% | 58.1% | -3.0% | -14.7% ± 1.8% |
| o/u1.5:over | 1588 | 76.1% | 73.9% | +2.2% | -3.9% ± 1.4% |
| o/u1.5:under | 1588 | 23.9% | 26.1% | -2.2% | -15.7% ± 4.0% |
| o/u2.5:over | 1986 | 54.9% | 53.4% | +1.5% | -4.4% ± 2.0% |
| o/u2.5:under | 1986 | 45.1% | 46.6% | -1.5% | -10.3% ± 2.3% |
| o/u3.5:over | 1820 | 34.9% | 35.7% | -0.7% | -8.3% ± 3.1% |
| o/u3.5:under | 1820 | 65.1% | 64.3% | +0.7% | -5.4% ± 1.7% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 157 | 81.5% | 77.9% | +3.6% | -3.5% ± 3.7% |
| 1x2 @ 1.30–1.60 | 377 | 66.8% | 63.2% | +3.7% | -2.5% ± 3.6% |
| 1x2 @ 1.60–2.00 | 639 | 56.5% | 51.5% | +5.0% | +0.7% ± 3.5% |
| 1x2 @ 2.00–3.00 | 1623 | 38.8% | 37.6% | +1.3% | -5.0% ± 3.0% |
| 1x2 @ 3.00–5.00 | 2827 | 23.2% | 25.4% | -2.2% | -16.6% ± 2.9% |
| 1x2 @ 5.00–1000.00 | 725 | 12.3% | 13.6% | -1.4% | -17.2% ± 8.9% |
| btts @ 1.00–1.30 | 38 | 63.2% | 73.3% | -10.1% | -21.6% ± 9.9% |
| btts @ 1.30–1.60 | 751 | 59.0% | 61.3% | -2.4% | -12.3% ± 2.7% |
| btts @ 1.60–2.00 | 1673 | 51.2% | 51.2% | -0.1% | -9.0% ± 2.2% |
| btts @ 2.00–3.00 | 1096 | 42.2% | 40.6% | +1.6% | -4.9% ± 3.4% |
| btts @ 3.00–5.00 | 52 | 38.5% | 27.7% | +10.8% | +27.5% ± 22.7% |
| dc @ 1.00–1.30 | 2767 | 80.5% | 77.1% | +3.4% | -3.6% ± 0.9% |
| dc @ 1.30–1.60 | 1997 | 65.9% | 66.0% | -0.1% | -7.8% ± 1.5% |
| dc @ 1.60–2.00 | 753 | 46.6% | 52.7% | -6.1% | -18.5% ± 3.2% |
| dc @ 2.00–3.00 | 452 | 33.4% | 40.2% | -6.8% | -23.0% ± 5.2% |
| dc @ 3.00–5.00 | 115 | 15.7% | 26.6% | -11.0% | -45.1% ± 12.1% |
| o/u1.5 @ 1.00–1.30 | 1005 | 80.4% | 78.2% | +2.2% | -3.8% ± 1.5% |
| o/u1.5 @ 1.30–1.60 | 550 | 69.1% | 67.2% | +1.9% | -4.4% ± 2.7% |
| o/u1.5 @ 1.60–2.00 | 38 | 65.8% | 54.8% | +11.0% | +12.4% ± 13.4% |
| o/u1.5 @ 2.00–3.00 | 357 | 34.5% | 35.7% | -1.2% | -9.0% ± 6.7% |
| o/u1.5 @ 3.00–5.00 | 985 | 22.8% | 25.0% | -2.2% | -14.0% ± 5.1% |
| o/u1.5 @ 5.00–1000.00 | 241 | 11.2% | 15.9% | -4.7% | -34.8% ± 12.1% |
| o/u2.5 @ 1.00–1.30 | 70 | 81.4% | 75.5% | +6.0% | +0.7% ± 5.8% |
| o/u2.5 @ 1.30–1.60 | 794 | 62.6% | 63.1% | -0.5% | -7.8% ± 2.5% |
| o/u2.5 @ 1.60–2.00 | 1606 | 53.2% | 52.3% | +1.0% | -5.5% ± 2.2% |
| o/u2.5 @ 2.00–3.00 | 1357 | 40.0% | 40.7% | -0.7% | -8.4% ± 3.1% |
| o/u2.5 @ 3.00–5.00 | 139 | 24.5% | 27.9% | -3.4% | -15.4% ± 12.8% |
| o/u3.5 @ 1.00–1.30 | 480 | 73.8% | 75.7% | -1.9% | -9.6% ± 2.5% |
| o/u3.5 @ 1.30–1.60 | 907 | 65.7% | 65.1% | +0.6% | -6.0% ± 2.3% |
| o/u3.5 @ 1.60–2.00 | 590 | 55.4% | 52.9% | +2.5% | -2.7% ± 3.6% |
| o/u3.5 @ 2.00–3.00 | 963 | 37.0% | 38.6% | -1.7% | -10.4% ± 3.8% |
| o/u3.5 @ 3.00–5.00 | 667 | 27.6% | 26.5% | +1.1% | -2.3% ± 6.2% |
| o/u3.5 @ 5.00–1000.00 | 33 | 9.1% | 16.4% | -7.3% | -49.1% ± 28.5% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Sweden · Division 2 — dc:1x | 37 | 59.5% | 71.4% | -11.9% | -22.6% ± 11.0% |
| Spain · Segunda Federacion — 1x2:away | 34 | 11.8% | 27.6% | -15.9% | -62.2% ± 18.4% |
| Sweden · Division 2 — 1x2:draw | 37 | 8.1% | 22.3% | -14.2% | -70.0% ± 16.8% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 645 | +0.0% | -9.7% |
| not covered | 1x2 | 5703 | +0.0% | -10.9% |
| covered | btts | 430 | +0.0% | -3.3% |
| not covered | btts | 3180 | +0.0% | -8.7% |
| covered | dc | 645 | +0.0% | -8.0% |
| not covered | dc | 5451 | -0.0% | -9.4% |
| covered | o/u1.5 | 424 | +0.0% | -5.6% |
| not covered | o/u1.5 | 2752 | +0.0% | -10.4% |
| covered | o/u2.5 | 430 | +0.0% | -4.6% |
| not covered | o/u2.5 | 3542 | +0.0% | -7.7% |
| covered | o/u3.5 | 430 | +0.0% | -5.7% |
| not covered | o/u3.5 | 3210 | +0.0% | -7.0% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 4295 | 48.2% | 47.8% | +0.4% | -0.3% ± 1.9% |
| steady | 14481 | 54.3% | 53.9% | +0.4% | -8.0% ± 0.8% |
| drifted 3%+ | 5542 | 38.8% | 40.1% | -1.2% | -18.9% ± 1.6% |

## Basketball — 373 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 371 | 51.5% | 50.2% | +1.3% | -4.8% ± 4.8% |
| hcp:home | 371 | 48.5% | 49.8% | -1.3% | -9.5% ± 4.8% |
| total:over | 371 | 53.1% | 50.1% | +3.0% | -1.5% ± 4.8% |
| total:under | 371 | 46.9% | 49.9% | -3.0% | -13.0% ± 4.8% |
| win:away | 371 | 43.1% | 43.5% | -0.4% | -8.8% ± 6.7% |
| win:home | 371 | 56.9% | 56.5% | +0.4% | -7.2% ± 5.3% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 740 | 50.0% | 50.0% | -0.0% | -7.2% ± 3.4% |
| total @ 1.60–2.00 | 741 | 50.1% | 50.0% | +0.1% | -7.1% ± 3.4% |
| win @ 1.00–1.30 | 141 | 83.0% | 82.3% | +0.7% | -6.1% ± 3.7% |
| win @ 1.30–1.60 | 132 | 62.1% | 65.4% | -3.3% | -11.6% ± 6.1% |
| win @ 1.60–2.00 | 126 | 50.0% | 53.2% | -3.2% | -11.6% ± 7.9% |
| win @ 2.00–3.00 | 166 | 45.2% | 39.7% | +5.4% | +6.2% ± 9.2% |
| win @ 3.00–5.00 | 100 | 28.0% | 25.8% | +2.2% | +4.4% ± 17.1% |
| win @ 5.00–1000.00 | 77 | 7.8% | 12.9% | -5.1% | -46.2% ± 21.7% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 30 | +0.0% | -6.9% |
| not covered | hcp | 712 | +0.0% | -7.2% |
| covered | total | 30 | +0.0% | -6.7% |
| not covered | total | 712 | +0.0% | -7.3% |
| covered | win | 30 | -0.0% | +2.2% |
| not covered | win | 712 | +0.0% | -8.4% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 328 | 50.3% | 49.7% | +0.6% | +5.8% ± 7.1% |
| steady | 1329 | 51.2% | 51.6% | -0.4% | -7.5% ± 2.7% |
| drifted 3%+ | 355 | 45.4% | 44.3% | +1.0% | -16.0% ± 5.2% |

