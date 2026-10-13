# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

2396 games graded (100% of 2396 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-13.

## Football — 2039 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 2023 | 31.8% | 32.2% | -0.4% | -11.0% ± 3.5% |
| 1x2:draw | 2023 | 23.3% | 25.0% | -1.6% | -15.5% ± 3.5% |
| 1x2:home | 2023 | 44.8% | 42.9% | +2.0% | -5.5% ± 2.8% |
| btts:no | 1722 | 46.0% | 45.9% | +0.1% | -7.7% ± 2.5% |
| btts:yes | 1722 | 54.0% | 54.1% | -0.1% | -8.5% ± 2.1% |
| dc:12 | 1942 | 76.7% | 37.1% | +39.6% | -4.7% ± 1.2% |
| dc:1x | 1942 | 68.1% | 33.8% | +34.3% | -8.3% ± 1.5% |
| dc:x2 | 1942 | 55.2% | 29.1% | +26.1% | -14.4% ± 1.9% |
| o/u1.5:over | 1510 | 75.6% | 74.0% | +1.6% | -4.6% ± 1.4% |
| o/u1.5:under | 1510 | 24.4% | 26.0% | -1.6% | -13.9% ± 4.1% |
| o/u2.5:over | 1899 | 54.3% | 53.4% | +0.9% | -5.7% ± 2.1% |
| o/u2.5:under | 1899 | 45.7% | 46.6% | -0.9% | -9.0% ± 2.4% |
| o/u3.5:over | 1740 | 34.4% | 35.7% | -1.3% | -9.8% ± 3.2% |
| o/u3.5:under | 1740 | 65.6% | 64.3% | +1.3% | -4.5% ± 1.7% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 142 | 80.3% | 77.6% | +2.7% | -4.7% ± 4.0% |
| 1x2 @ 1.30–1.60 | 358 | 66.8% | 63.1% | +3.6% | -2.6% ± 3.7% |
| 1x2 @ 1.60–2.00 | 613 | 56.1% | 51.5% | +4.6% | +0.0% ± 3.6% |
| 1x2 @ 2.00–3.00 | 1567 | 38.8% | 37.6% | +1.2% | -5.1% ± 3.0% |
| 1x2 @ 3.00–5.00 | 2717 | 23.4% | 25.4% | -2.0% | -16.0% ± 3.0% |
| 1x2 @ 5.00–1000.00 | 672 | 12.4% | 13.8% | -1.4% | -17.7% ± 9.1% |
| btts @ 1.00–1.30 | 36 | 63.9% | 73.2% | -9.3% | -20.6% ± 10.1% |
| btts @ 1.30–1.60 | 708 | 59.3% | 61.3% | -2.0% | -11.8% ± 2.8% |
| btts @ 1.60–2.00 | 1612 | 51.1% | 51.2% | -0.1% | -9.1% ± 2.2% |
| btts @ 2.00–3.00 | 1039 | 42.0% | 40.6% | +1.4% | -5.4% ± 3.5% |
| btts @ 3.00–5.00 | 49 | 38.8% | 27.7% | +11.1% | +28.5% ± 23.5% |
| dc @ 1.00–1.30 | 2631 | 80.2% | 38.5% | +41.7% | -3.9% ± 0.9% |
| dc @ 1.30–1.60 | 1933 | 65.9% | 33.0% | +32.9% | -7.8% ± 1.5% |
| dc @ 1.60–2.00 | 717 | 46.9% | 26.4% | +20.5% | -18.1% ± 3.3% |
| dc @ 2.00–3.00 | 429 | 33.8% | 20.2% | +13.6% | -22.4% ± 5.3% |
| dc @ 3.00–5.00 | 106 | 17.0% | 13.3% | +3.7% | -40.5% ± 13.0% |
| o/u1.5 @ 1.00–1.30 | 959 | 80.1% | 78.2% | +1.9% | -4.2% ± 1.6% |
| o/u1.5 @ 1.30–1.60 | 521 | 68.3% | 67.3% | +1.0% | -5.7% ± 2.8% |
| o/u1.5 @ 1.60–2.00 | 35 | 65.7% | 54.5% | +11.2% | +12.8% ± 14.1% |
| o/u1.5 @ 2.00–3.00 | 329 | 35.6% | 35.6% | +0.0% | -5.8% ± 7.1% |
| o/u1.5 @ 3.00–5.00 | 948 | 23.2% | 25.0% | -1.8% | -12.6% ± 5.2% |
| o/u1.5 @ 5.00–1000.00 | 228 | 11.4% | 15.9% | -4.5% | -33.3% ± 12.6% |
| o/u2.5 @ 1.00–1.30 | 67 | 82.1% | 75.2% | +6.9% | +1.8% ± 5.9% |
| o/u2.5 @ 1.30–1.60 | 746 | 62.7% | 63.0% | -0.3% | -7.5% ± 2.6% |
| o/u2.5 @ 1.60–2.00 | 1553 | 53.1% | 52.3% | +0.8% | -5.7% ± 2.3% |
| o/u2.5 @ 2.00–3.00 | 1296 | 40.0% | 40.8% | -0.8% | -8.8% ± 3.1% |
| o/u2.5 @ 3.00–5.00 | 131 | 25.2% | 27.9% | -2.7% | -13.6% ± 13.2% |
| o/u3.5 @ 1.00–1.30 | 458 | 74.0% | 75.6% | -1.6% | -9.2% ± 2.5% |
| o/u3.5 @ 1.30–1.60 | 870 | 66.2% | 65.1% | +1.1% | -5.2% ± 2.3% |
| o/u3.5 @ 1.60–2.00 | 559 | 55.8% | 52.9% | +2.9% | -2.2% ± 3.7% |
| o/u3.5 @ 2.00–3.00 | 928 | 36.3% | 38.6% | -2.3% | -12.0% ± 3.9% |
| o/u3.5 @ 3.00–5.00 | 636 | 27.2% | 26.5% | +0.7% | -4.0% ± 6.3% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Sweden · Division 2 — dc:1x | 37 | 59.5% | 35.7% | +23.8% | -22.6% ± 11.0% |
| Spain · Segunda Federacion — 1x2:away | 34 | 11.8% | 27.6% | -15.9% | -62.2% ± 18.4% |
| Sweden · Division 2 — 1x2:draw | 37 | 8.1% | 22.3% | -14.2% | -70.0% ± 16.8% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 645 | +0.0% | -9.7% |
| not covered | 1x2 | 5424 | +0.0% | -10.8% |
| covered | btts | 430 | +0.0% | -3.3% |
| not covered | btts | 3014 | +0.0% | -8.8% |
| covered | dc | 645 | +33.3% | -8.0% |
| not covered | dc | 5181 | +33.3% | -9.3% |
| covered | o/u1.5 | 424 | +0.0% | -5.6% |
| not covered | o/u1.5 | 2596 | +0.0% | -9.8% |
| covered | o/u2.5 | 430 | +0.0% | -4.6% |
| not covered | o/u2.5 | 3368 | +0.0% | -7.7% |
| covered | o/u3.5 | 430 | +0.0% | -5.7% |
| not covered | o/u3.5 | 3050 | +0.0% | -7.4% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 4067 | 47.8% | 41.5% | +6.3% | -1.0% ± 1.9% |
| steady | 13951 | 54.2% | 44.2% | +10.0% | -8.0% ± 0.8% |
| drifted 3%+ | 5259 | 39.2% | 35.4% | +3.7% | -18.3% ± 1.7% |

## Basketball — 357 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 355 | 51.8% | 50.2% | +1.7% | -4.1% ± 4.9% |
| hcp:home | 355 | 48.2% | 49.8% | -1.7% | -10.2% ± 5.0% |
| total:over | 355 | 52.7% | 50.1% | +2.6% | -2.3% ± 4.9% |
| total:under | 355 | 47.3% | 49.9% | -2.6% | -12.2% ± 4.9% |
| win:away | 355 | 43.9% | 43.4% | +0.6% | -6.4% ± 6.9% |
| win:home | 355 | 56.1% | 56.6% | -0.6% | -9.2% ± 5.3% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 708 | 50.0% | 50.0% | -0.0% | -7.2% ± 3.5% |
| total @ 1.60–2.00 | 709 | 50.1% | 50.0% | +0.1% | -7.1% ± 3.5% |
| win @ 1.00–1.30 | 132 | 82.6% | 82.2% | +0.4% | -6.5% ± 3.8% |
| win @ 1.30–1.60 | 128 | 62.5% | 65.3% | -2.8% | -11.0% ± 6.1% |
| win @ 1.60–2.00 | 122 | 50.0% | 53.2% | -3.2% | -11.6% ± 8.1% |
| win @ 2.00–3.00 | 161 | 44.7% | 39.8% | +4.9% | +4.5% ± 9.3% |
| win @ 3.00–5.00 | 96 | 28.1% | 25.8% | +2.3% | +3.6% ± 17.2% |
| win @ 5.00–1000.00 | 71 | 8.5% | 12.8% | -4.3% | -41.6% ± 23.5% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

None yet — a competition needs 30+ graded games of a side, and a return two standard errors from zero, to be listed.

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 30 | +0.0% | -6.9% |
| not covered | hcp | 680 | +0.0% | -7.2% |
| covered | total | 30 | +0.0% | -6.7% |
| not covered | total | 680 | +0.0% | -7.3% |
| covered | win | 30 | -0.0% | +2.2% |
| not covered | win | 680 | +0.0% | -8.3% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 314 | 49.7% | 49.7% | +0.0% | +4.4% ± 7.2% |
| steady | 1269 | 51.1% | 51.6% | -0.4% | -7.4% ± 2.7% |
| drifted 3%+ | 341 | 46.0% | 44.4% | +1.6% | -14.9% ± 5.3% |

