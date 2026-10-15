# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

2842 games graded (99% of 2882 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-15.

## Football — 2380 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 2353 | 32.1% | 32.2% | -0.1% | -11.1% ± 3.2% |
| 1x2:draw | 2353 | 22.7% | 24.8% | -2.1% | -16.8% ± 3.3% |
| 1x2:home | 2353 | 45.2% | 43.1% | +2.1% | -4.6% ± 2.8% |
| btts:no | 2027 | 45.8% | 45.9% | -0.1% | -7.8% ± 2.3% |
| btts:yes | 2027 | 54.2% | 54.1% | +0.1% | -8.0% ± 1.9% |
| dc:12 | 2266 | 77.4% | 74.4% | +3.0% | -4.0% ± 1.1% |
| dc:1x | 2266 | 67.9% | 67.6% | +0.2% | -8.7% ± 1.4% |
| dc:x2 | 2266 | 54.8% | 58.0% | -3.2% | -15.4% ± 1.7% |
| o/u1.5:over | 1783 | 76.3% | 74.2% | +2.1% | -4.0% ± 1.3% |
| o/u1.5:under | 1783 | 23.7% | 25.8% | -2.1% | -14.9% ± 3.8% |
| o/u2.5:over | 2217 | 55.2% | 53.8% | +1.4% | -4.5% ± 1.9% |
| o/u2.5:under | 2217 | 44.8% | 46.2% | -1.4% | -9.9% ± 2.2% |
| o/u3.5:over | 2045 | 35.8% | 36.0% | -0.2% | -6.8% ± 2.9% |
| o/u3.5:under | 2045 | 64.2% | 64.0% | +0.2% | -6.1% ± 1.6% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 187 | 81.3% | 78.4% | +2.9% | -4.0% ± 3.4% |
| 1x2 @ 1.30–1.60 | 418 | 68.4% | 63.4% | +5.1% | -0.3% ± 3.3% |
| 1x2 @ 1.60–2.00 | 705 | 57.2% | 51.5% | +5.6% | +2.0% ± 3.3% |
| 1x2 @ 2.00–3.00 | 1783 | 38.9% | 37.7% | +1.3% | -5.0% ± 2.9% |
| 1x2 @ 3.00–5.00 | 3119 | 23.0% | 25.4% | -2.4% | -17.4% ± 2.7% |
| 1x2 @ 5.00–1000.00 | 847 | 11.8% | 13.5% | -1.7% | -16.5% ± 8.8% |
| btts @ 1.00–1.30 | 40 | 65.0% | 73.5% | -8.5% | -19.5% ± 9.5% |
| btts @ 1.30–1.60 | 858 | 58.7% | 61.5% | -2.8% | -12.8% ± 2.5% |
| btts @ 1.60–2.00 | 1850 | 51.6% | 51.3% | +0.3% | -8.3% ± 2.1% |
| btts @ 2.00–3.00 | 1242 | 41.6% | 40.5% | +1.1% | -5.6% ± 3.2% |
| btts @ 3.00–5.00 | 64 | 40.6% | 28.0% | +12.7% | +32.8% ± 20.3% |
| dc @ 1.00–1.30 | 3098 | 81.0% | 77.3% | +3.7% | -3.2% ± 0.9% |
| dc @ 1.30–1.60 | 2199 | 65.9% | 66.1% | -0.1% | -7.8% ± 1.4% |
| dc @ 1.60–2.00 | 841 | 46.1% | 52.8% | -6.6% | -19.3% ± 3.0% |
| dc @ 2.00–3.00 | 502 | 32.3% | 40.2% | -8.0% | -25.7% ± 4.9% |
| dc @ 3.00–5.00 | 141 | 15.6% | 26.6% | -11.0% | -44.6% ± 11.0% |
| o/u1.5 @ 1.00–1.30 | 1149 | 80.2% | 78.4% | +1.8% | -4.2% ± 1.4% |
| o/u1.5 @ 1.30–1.60 | 597 | 69.8% | 67.3% | +2.6% | -3.4% ± 2.6% |
| o/u1.5 @ 1.60–2.00 | 43 | 62.8% | 54.6% | +8.2% | +7.9% ± 12.9% |
| o/u1.5 @ 2.00–3.00 | 383 | 34.5% | 35.7% | -1.2% | -9.2% ± 6.5% |
| o/u1.5 @ 3.00–5.00 | 1091 | 22.6% | 25.0% | -2.4% | -14.6% ± 4.8% |
| o/u1.5 @ 5.00–1000.00 | 303 | 12.5% | 15.7% | -3.2% | -25.4% ± 11.6% |
| o/u2.5 @ 1.00–1.30 | 90 | 80.0% | 75.7% | +4.3% | -1.0% ± 5.3% |
| o/u2.5 @ 1.30–1.60 | 898 | 63.1% | 63.2% | -0.1% | -7.1% ± 2.4% |
| o/u2.5 @ 1.60–2.00 | 1759 | 53.1% | 52.3% | +0.8% | -5.7% ± 2.1% |
| o/u2.5 @ 2.00–3.00 | 1494 | 40.0% | 40.7% | -0.8% | -8.5% ± 2.9% |
| o/u2.5 @ 3.00–5.00 | 184 | 25.0% | 27.9% | -2.9% | -13.7% ± 11.2% |
| o/u3.5 @ 1.00–1.30 | 523 | 73.6% | 75.7% | -2.1% | -9.8% ± 2.4% |
| o/u3.5 @ 1.30–1.60 | 1018 | 64.7% | 65.1% | -0.3% | -7.4% ± 2.2% |
| o/u3.5 @ 1.60–2.00 | 686 | 55.0% | 52.9% | +2.1% | -3.3% ± 3.4% |
| o/u3.5 @ 2.00–3.00 | 1098 | 38.1% | 38.7% | -0.6% | -7.8% ± 3.6% |
| o/u3.5 @ 3.00–5.00 | 728 | 27.9% | 26.5% | +1.4% | -1.3% ± 5.9% |
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
| covered | 1x2 | 732 | -0.0% | -8.0% |
| not covered | 1x2 | 6327 | -0.0% | -11.2% |
| covered | btts | 488 | +0.0% | -3.1% |
| not covered | btts | 3566 | +0.0% | -8.6% |
| covered | dc | 732 | +0.0% | -7.5% |
| not covered | dc | 6066 | -0.0% | -9.6% |
| covered | o/u1.5 | 482 | +0.0% | -5.1% |
| not covered | o/u1.5 | 3084 | +0.0% | -10.1% |
| covered | o/u2.5 | 488 | +0.0% | -4.8% |
| not covered | o/u2.5 | 3946 | +0.0% | -7.5% |
| covered | o/u3.5 | 488 | +0.0% | -4.0% |
| not covered | o/u3.5 | 3602 | +0.0% | -6.8% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 4787 | 48.3% | 47.9% | +0.5% | +0.3% ± 1.8% |
| steady | 15837 | 54.4% | 54.0% | +0.4% | -8.0% ± 0.8% |
| drifted 3%+ | 6245 | 38.7% | 40.0% | -1.3% | -19.3% ± 1.5% |

## Basketball — 462 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 460 | 51.5% | 50.1% | +1.4% | -4.6% ± 4.3% |
| hcp:home | 460 | 48.5% | 49.9% | -1.4% | -9.5% ± 4.4% |
| total:over | 460 | 53.3% | 50.1% | +3.2% | -1.2% ± 4.3% |
| total:under | 460 | 46.7% | 49.9% | -3.2% | -13.2% ± 4.3% |
| win:away | 460 | 44.3% | 43.5% | +0.8% | -5.9% ± 6.2% |
| win:home | 460 | 55.7% | 56.5% | -0.8% | -10.0% ± 4.7% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 915 | 50.1% | 50.0% | +0.0% | -7.0% ± 3.1% |
| total @ 1.60–2.00 | 919 | 50.1% | 50.0% | +0.0% | -7.1% ± 3.1% |
| win @ 1.00–1.30 | 171 | 81.9% | 82.3% | -0.5% | -7.6% ± 3.4% |
| win @ 1.30–1.60 | 171 | 66.1% | 65.7% | +0.4% | -6.0% ± 5.2% |
| win @ 1.60–2.00 | 149 | 49.7% | 53.5% | -3.8% | -12.5% ± 7.3% |
| win @ 2.00–3.00 | 206 | 42.7% | 39.6% | +3.1% | +0.4% ± 8.2% |
| win @ 3.00–5.00 | 129 | 28.7% | 26.1% | +2.6% | +4.8% ± 14.8% |
| win @ 5.00–1000.00 | 94 | 8.5% | 12.8% | -4.3% | -40.7% ± 20.7% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 58 | +0.0% | -6.7% |
| not covered | hcp | 862 | +0.0% | -7.1% |
| covered | total | 58 | +0.0% | -7.0% |
| not covered | total | 862 | +0.0% | -7.2% |
| covered | win | 58 | -0.0% | -5.7% |
| not covered | win | 862 | +0.0% | -8.1% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 406 | 50.0% | 49.6% | +0.4% | +3.6% ± 6.1% |
| steady | 1663 | 51.5% | 51.6% | -0.1% | -6.9% ± 2.4% |
| drifted 3%+ | 439 | 44.4% | 44.3% | +0.1% | -16.7% ± 5.0% |

