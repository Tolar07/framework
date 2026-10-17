# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

3076 games graded (91% of 3368 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-17.

## Football — 2559 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 2530 | 32.2% | 32.2% | -0.0% | -11.4% ± 3.1% |
| 1x2:draw | 2530 | 22.6% | 24.7% | -2.1% | -17.0% ± 3.2% |
| 1x2:home | 2530 | 45.2% | 43.1% | +2.1% | -4.8% ± 2.7% |
| btts:no | 2188 | 45.2% | 45.9% | -0.8% | -9.2% ± 2.2% |
| btts:yes | 2188 | 54.8% | 54.1% | +0.8% | -6.7% ± 1.9% |
| dc:12 | 2439 | 77.5% | 74.4% | +3.0% | -3.9% ± 1.1% |
| dc:1x | 2439 | 67.7% | 67.6% | +0.1% | -8.9% ± 1.4% |
| dc:x2 | 2439 | 54.8% | 58.0% | -3.2% | -15.4% ± 1.7% |
| o/u1.5:over | 1935 | 76.8% | 74.3% | +2.5% | -3.5% ± 1.2% |
| o/u1.5:under | 1935 | 23.2% | 25.7% | -2.5% | -16.6% ± 3.7% |
| o/u2.5:over | 2389 | 55.8% | 53.9% | +1.9% | -3.6% ± 1.8% |
| o/u2.5:under | 2389 | 44.2% | 46.1% | -1.9% | -11.1% ± 2.2% |
| o/u3.5:over | 2200 | 36.1% | 36.0% | +0.1% | -6.0% ± 2.8% |
| o/u3.5:under | 2200 | 63.9% | 64.0% | -0.1% | -6.5% ± 1.6% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 207 | 82.6% | 78.5% | +4.1% | -2.4% ± 3.2% |
| 1x2 @ 1.30–1.60 | 460 | 68.9% | 63.4% | +5.5% | +0.3% ± 3.2% |
| 1x2 @ 1.60–2.00 | 748 | 56.3% | 51.6% | +4.7% | +0.4% ± 3.3% |
| 1x2 @ 2.00–3.00 | 1904 | 38.9% | 37.7% | +1.3% | -4.9% ± 2.8% |
| 1x2 @ 3.00–5.00 | 3330 | 23.2% | 25.4% | -2.2% | -16.5% ± 2.7% |
| 1x2 @ 5.00–1000.00 | 941 | 11.4% | 13.5% | -2.1% | -20.5% ± 8.1% |
| btts @ 1.00–1.30 | 41 | 65.9% | 73.5% | -7.7% | -18.6% ± 9.3% |
| btts @ 1.30–1.60 | 913 | 59.4% | 61.5% | -2.2% | -11.8% ± 2.4% |
| btts @ 1.60–2.00 | 2014 | 51.4% | 51.3% | +0.1% | -8.5% ± 2.0% |
| btts @ 2.00–3.00 | 1341 | 41.5% | 40.6% | +0.9% | -6.0% ± 3.1% |
| btts @ 3.00–5.00 | 67 | 38.8% | 27.9% | +10.9% | +26.8% ± 19.7% |
| dc @ 1.00–1.30 | 3337 | 81.1% | 77.4% | +3.7% | -3.2% ± 0.8% |
| dc @ 1.30–1.60 | 2356 | 65.9% | 66.1% | -0.2% | -7.9% ± 1.4% |
| dc @ 1.60–2.00 | 897 | 46.7% | 52.8% | -6.1% | -18.3% ± 2.9% |
| dc @ 2.00–3.00 | 549 | 32.2% | 40.2% | -8.0% | -25.8% ± 4.6% |
| dc @ 3.00–5.00 | 160 | 14.4% | 26.4% | -12.1% | -49.1% ± 10.0% |
| o/u1.5 @ 1.00–1.30 | 1255 | 81.0% | 78.5% | +2.5% | -3.3% ± 1.3% |
| o/u1.5 @ 1.30–1.60 | 641 | 69.9% | 67.3% | +2.6% | -3.4% ± 2.5% |
| o/u1.5 @ 1.60–2.00 | 47 | 61.7% | 54.2% | +7.5% | +7.2% ± 12.6% |
| o/u1.5 @ 2.00–3.00 | 402 | 33.8% | 35.7% | -1.9% | -11.1% ± 6.3% |
| o/u1.5 @ 3.00–5.00 | 1179 | 22.4% | 25.0% | -2.6% | -15.8% ± 4.6% |
| o/u1.5 @ 5.00–1000.00 | 346 | 11.8% | 15.7% | -3.9% | -28.5% ± 10.8% |
| o/u2.5 @ 1.00–1.30 | 97 | 80.4% | 75.7% | +4.7% | -0.4% ± 5.0% |
| o/u2.5 @ 1.30–1.60 | 970 | 63.3% | 63.3% | +0.0% | -6.9% ± 2.3% |
| o/u2.5 @ 1.60–2.00 | 1892 | 53.3% | 52.3% | +1.0% | -5.4% ± 2.0% |
| o/u2.5 @ 2.00–3.00 | 1610 | 39.8% | 40.7% | -0.9% | -8.8% ± 2.8% |
| o/u2.5 @ 3.00–5.00 | 200 | 23.5% | 27.9% | -4.4% | -18.4% ± 10.6% |
| o/u3.5 @ 1.00–1.30 | 550 | 73.3% | 75.7% | -2.4% | -10.2% ± 2.3% |
| o/u3.5 @ 1.30–1.60 | 1102 | 64.5% | 65.1% | -0.6% | -7.7% ± 2.1% |
| o/u3.5 @ 1.60–2.00 | 742 | 54.9% | 52.9% | +1.9% | -3.5% ± 3.2% |
| o/u3.5 @ 2.00–3.00 | 1189 | 38.4% | 38.7% | -0.3% | -7.1% ± 3.4% |
| o/u3.5 @ 3.00–5.00 | 780 | 28.2% | 26.5% | +1.7% | -0.3% ± 5.8% |
| o/u3.5 @ 5.00–1000.00 | 37 | 8.1% | 16.3% | -8.2% | -54.6% ± 25.5% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Sweden · Division 2 — dc:1x | 37 | 59.5% | 71.4% | -11.9% | -22.6% ± 11.0% |
| Spain · Segunda Federacion — 1x2:away | 34 | 11.8% | 27.6% | -15.9% | -62.2% ± 18.4% |
| Sweden · Division 2 — 1x2:draw | 37 | 8.1% | 22.3% | -14.2% | -70.0% ± 16.8% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 822 | -0.0% | -9.7% |
| not covered | 1x2 | 6768 | -0.0% | -11.2% |
| covered | btts | 546 | +0.0% | -3.2% |
| not covered | btts | 3830 | +0.0% | -8.7% |
| covered | dc | 822 | +0.0% | -8.1% |
| not covered | dc | 6495 | -0.0% | -9.6% |
| covered | o/u1.5 | 542 | +0.0% | -6.2% |
| not covered | o/u1.5 | 3328 | +0.0% | -10.7% |
| covered | o/u2.5 | 548 | +0.0% | -5.2% |
| not covered | o/u2.5 | 4230 | +0.0% | -7.6% |
| covered | o/u3.5 | 548 | +0.0% | -4.7% |
| not covered | o/u3.5 | 3852 | +0.0% | -6.4% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 5224 | 49.1% | 48.0% | +1.1% | +2.0% ± 1.7% |
| steady | 16935 | 54.5% | 54.1% | +0.4% | -7.9% ± 0.8% |
| drifted 3%+ | 6849 | 38.1% | 39.9% | -1.9% | -21.0% ± 1.4% |

## Basketball — 517 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 515 | 51.7% | 50.1% | +1.5% | -4.3% ± 4.1% |
| hcp:home | 515 | 48.3% | 49.9% | -1.5% | -9.9% ± 4.1% |
| total:over | 514 | 53.7% | 50.1% | +3.6% | -0.4% ± 4.1% |
| total:under | 514 | 46.3% | 49.9% | -3.6% | -14.1% ± 4.1% |
| win:away | 515 | 44.9% | 43.7% | +1.1% | -5.2% ± 5.8% |
| win:home | 515 | 55.1% | 56.3% | -1.1% | -10.4% ± 4.4% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 1025 | 50.0% | 50.0% | +0.0% | -7.0% ± 2.9% |
| total @ 1.60–2.00 | 1027 | 50.0% | 50.0% | +0.0% | -7.1% ± 2.9% |
| win @ 1.00–1.30 | 189 | 82.0% | 82.2% | -0.2% | -7.3% ± 3.2% |
| win @ 1.30–1.60 | 197 | 64.5% | 65.7% | -1.3% | -8.5% ± 4.9% |
| win @ 1.60–2.00 | 163 | 48.5% | 53.4% | -4.9% | -14.5% ± 7.0% |
| win @ 2.00–3.00 | 233 | 43.8% | 39.4% | +4.3% | +3.1% ± 7.8% |
| win @ 3.00–5.00 | 144 | 30.6% | 26.2% | +4.3% | +10.4% ± 14.1% |
| win @ 5.00–1000.00 | 104 | 7.7% | 12.9% | -5.2% | -46.4% ± 18.8% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 70 | +0.0% | -6.5% |
| not covered | hcp | 960 | +0.0% | -7.1% |
| covered | total | 70 | +0.0% | -6.8% |
| not covered | total | 958 | +0.0% | -7.2% |
| covered | win | 70 | +0.0% | -4.1% |
| not covered | win | 960 | +0.0% | -8.1% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 474 | 50.2% | 49.7% | +0.5% | +4.1% ± 5.6% |
| steady | 1838 | 51.5% | 51.6% | -0.1% | -7.1% ± 2.2% |
| drifted 3%+ | 506 | 44.5% | 44.5% | -0.0% | -16.3% ± 4.6% |

