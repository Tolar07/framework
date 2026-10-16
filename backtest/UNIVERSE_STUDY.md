# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

2977 games graded (95% of 3149 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-16.

## Football — 2485 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 2456 | 32.2% | 32.1% | +0.1% | -10.9% ± 3.1% |
| 1x2:draw | 2456 | 22.6% | 24.7% | -2.0% | -16.9% ± 3.2% |
| 1x2:home | 2456 | 45.2% | 43.2% | +1.9% | -5.3% ± 2.7% |
| btts:no | 2125 | 45.3% | 45.9% | -0.6% | -8.9% ± 2.2% |
| btts:yes | 2125 | 54.7% | 54.1% | +0.6% | -6.9% ± 1.9% |
| dc:12 | 2367 | 77.4% | 74.5% | +3.0% | -4.0% ± 1.1% |
| dc:1x | 2367 | 67.7% | 67.7% | +0.0% | -9.1% ± 1.4% |
| dc:x2 | 2367 | 54.8% | 57.8% | -3.0% | -15.2% ± 1.7% |
| o/u1.5:over | 1878 | 76.9% | 74.4% | +2.5% | -3.4% ± 1.2% |
| o/u1.5:under | 1878 | 23.1% | 25.6% | -2.5% | -16.8% ± 3.7% |
| o/u2.5:over | 2318 | 55.7% | 53.9% | +1.8% | -3.8% ± 1.9% |
| o/u2.5:under | 2318 | 44.3% | 46.1% | -1.8% | -10.7% ± 2.2% |
| o/u3.5:over | 2140 | 35.9% | 36.0% | -0.1% | -6.5% ± 2.9% |
| o/u3.5:under | 2140 | 64.1% | 64.0% | +0.1% | -6.2% ± 1.6% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 202 | 82.2% | 78.5% | +3.7% | -2.9% ± 3.2% |
| 1x2 @ 1.30–1.60 | 445 | 68.8% | 63.4% | +5.3% | +0.1% ± 3.2% |
| 1x2 @ 1.60–2.00 | 728 | 56.6% | 51.6% | +5.0% | +1.0% ± 3.3% |
| 1x2 @ 2.00–3.00 | 1846 | 39.0% | 37.7% | +1.3% | -4.7% ± 2.8% |
| 1x2 @ 3.00–5.00 | 3232 | 23.1% | 25.4% | -2.3% | -17.1% ± 2.7% |
| 1x2 @ 5.00–1000.00 | 915 | 11.6% | 13.5% | -1.9% | -18.8% ± 8.3% |
| btts @ 1.00–1.30 | 41 | 65.9% | 73.5% | -7.7% | -18.6% ± 9.3% |
| btts @ 1.30–1.60 | 890 | 59.1% | 61.5% | -2.4% | -12.2% ± 2.5% |
| btts @ 1.60–2.00 | 1948 | 51.5% | 51.3% | +0.2% | -8.4% ± 2.0% |
| btts @ 2.00–3.00 | 1304 | 41.6% | 40.6% | +1.1% | -5.6% ± 3.1% |
| btts @ 3.00–5.00 | 67 | 38.8% | 27.9% | +10.9% | +26.8% ± 19.7% |
| dc @ 1.00–1.30 | 3245 | 81.1% | 77.4% | +3.7% | -3.1% ± 0.8% |
| dc @ 1.30–1.60 | 2277 | 65.9% | 66.1% | -0.2% | -7.9% ± 1.4% |
| dc @ 1.60–2.00 | 871 | 46.6% | 52.8% | -6.2% | -18.5% ± 3.0% |
| dc @ 2.00–3.00 | 534 | 32.2% | 40.2% | -8.0% | -25.8% ± 4.7% |
| dc @ 3.00–5.00 | 156 | 14.7% | 26.4% | -11.7% | -47.8% ± 10.2% |
| o/u1.5 @ 1.00–1.30 | 1219 | 81.0% | 78.5% | +2.4% | -3.4% ± 1.4% |
| o/u1.5 @ 1.30–1.60 | 622 | 70.1% | 67.3% | +2.8% | -3.1% ± 2.5% |
| o/u1.5 @ 1.60–2.00 | 43 | 62.8% | 54.6% | +8.2% | +7.9% ± 12.9% |
| o/u1.5 @ 2.00–3.00 | 393 | 34.4% | 35.7% | -1.3% | -9.8% ± 6.3% |
| o/u1.5 @ 3.00–5.00 | 1142 | 22.2% | 25.0% | -2.9% | -16.5% ± 4.7% |
| o/u1.5 @ 5.00–1000.00 | 337 | 11.9% | 15.7% | -3.8% | -28.1% ± 11.0% |
| o/u2.5 @ 1.00–1.30 | 94 | 79.8% | 75.8% | +4.0% | -1.3% ± 5.2% |
| o/u2.5 @ 1.30–1.60 | 944 | 63.3% | 63.3% | +0.1% | -6.8% ± 2.3% |
| o/u2.5 @ 1.60–2.00 | 1830 | 53.2% | 52.3% | +0.9% | -5.6% ± 2.1% |
| o/u2.5 @ 2.00–3.00 | 1564 | 39.9% | 40.7% | -0.8% | -8.6% ± 2.9% |
| o/u2.5 @ 3.00–5.00 | 195 | 24.1% | 27.9% | -3.8% | -16.3% ± 10.8% |
| o/u3.5 @ 1.00–1.30 | 539 | 73.5% | 75.7% | -2.2% | -10.0% ± 2.3% |
| o/u3.5 @ 1.30–1.60 | 1066 | 64.8% | 65.1% | -0.3% | -7.2% ± 2.1% |
| o/u3.5 @ 1.60–2.00 | 724 | 55.0% | 52.9% | +2.0% | -3.3% ± 3.3% |
| o/u3.5 @ 2.00–3.00 | 1155 | 38.1% | 38.7% | -0.6% | -7.7% ± 3.5% |
| o/u3.5 @ 3.00–5.00 | 759 | 27.9% | 26.5% | +1.4% | -1.3% ± 5.8% |
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
| not covered | 1x2 | 6546 | -0.0% | -11.2% |
| covered | btts | 546 | +0.0% | -3.2% |
| not covered | btts | 3704 | +0.0% | -8.6% |
| covered | dc | 822 | +0.0% | -8.1% |
| not covered | dc | 6279 | -0.0% | -9.6% |
| covered | o/u1.5 | 542 | +0.0% | -6.2% |
| not covered | o/u1.5 | 3214 | +0.0% | -10.7% |
| covered | o/u2.5 | 548 | +0.0% | -5.2% |
| not covered | o/u2.5 | 4088 | +0.0% | -7.6% |
| covered | o/u3.5 | 548 | +0.0% | -4.7% |
| not covered | o/u3.5 | 3732 | +0.0% | -6.6% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 5046 | 48.9% | 48.1% | +0.8% | +1.5% ± 1.8% |
| steady | 16462 | 54.5% | 54.1% | +0.4% | -7.9% ± 0.8% |
| drifted 3%+ | 6621 | 38.2% | 39.9% | -1.7% | -20.6% ± 1.5% |

## Basketball — 492 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 490 | 51.8% | 50.1% | +1.7% | -4.0% ± 4.2% |
| hcp:home | 490 | 48.2% | 49.9% | -1.7% | -10.1% ± 4.2% |
| total:over | 490 | 53.9% | 50.1% | +3.8% | -0.0% ± 4.2% |
| total:under | 490 | 46.1% | 49.9% | -3.8% | -14.4% ± 4.2% |
| win:away | 490 | 44.9% | 43.5% | +1.4% | -4.8% ± 6.0% |
| win:home | 490 | 55.1% | 56.5% | -1.4% | -11.1% ± 4.5% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 975 | 50.1% | 50.0% | +0.0% | -7.0% ± 3.0% |
| total @ 1.60–2.00 | 979 | 50.1% | 50.0% | +0.0% | -7.1% ± 3.0% |
| win @ 1.00–1.30 | 185 | 82.2% | 82.3% | -0.1% | -7.2% ± 3.2% |
| win @ 1.30–1.60 | 181 | 64.6% | 65.6% | -1.0% | -8.0% ± 5.1% |
| win @ 1.60–2.00 | 156 | 49.4% | 53.4% | -4.1% | -13.0% ± 7.1% |
| win @ 2.00–3.00 | 218 | 43.6% | 39.7% | +3.9% | +2.4% ± 8.0% |
| win @ 3.00–5.00 | 137 | 29.9% | 26.2% | +3.7% | +8.7% ± 14.5% |
| win @ 5.00–1000.00 | 103 | 7.8% | 12.9% | -5.1% | -45.9% ± 19.0% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 70 | +0.0% | -6.5% |
| not covered | hcp | 910 | +0.0% | -7.1% |
| covered | total | 70 | +0.0% | -6.8% |
| not covered | total | 910 | +0.0% | -7.2% |
| covered | win | 70 | +0.0% | -4.1% |
| not covered | win | 910 | +0.0% | -8.3% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 439 | 49.7% | 49.5% | +0.2% | +3.5% ± 5.9% |
| steady | 1772 | 51.5% | 51.6% | -0.1% | -7.1% ± 2.3% |
| drifted 3%+ | 469 | 44.8% | 44.4% | +0.3% | -15.7% ± 4.8% |

