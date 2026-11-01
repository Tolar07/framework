# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

9822 games graded (70% of 14049 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-11-01.

## Football — 8162 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 8018 | 31.8% | 32.4% | -0.6% | -13.2% ± 1.7% |
| 1x2:draw | 8018 | 23.4% | 24.6% | -1.3% | -14.2% ± 1.8% |
| 1x2:home | 8018 | 44.9% | 43.0% | +1.9% | -4.5% ± 1.5% |
| btts:no | 6867 | 44.0% | 45.7% | -1.7% | -11.6% ± 1.2% |
| btts:yes | 6867 | 56.0% | 54.3% | +1.7% | -5.3% ± 1.0% |
| dc:12 | 7673 | 76.7% | 74.5% | +2.2% | -4.9% ± 0.6% |
| dc:1x | 7673 | 68.1% | 67.5% | +0.7% | -8.3% ± 0.8% |
| dc:x2 | 7673 | 55.1% | 58.0% | -2.9% | -14.1% ± 1.0% |
| o/u1.5:over | 6118 | 77.2% | 74.6% | +2.5% | -3.4% ± 0.7% |
| o/u1.5:under | 6118 | 22.8% | 25.4% | -2.5% | -16.9% ± 2.1% |
| o/u2.5:over | 7541 | 56.4% | 54.1% | +2.2% | -3.1% ± 1.0% |
| o/u2.5:under | 7541 | 43.6% | 45.9% | -2.2% | -11.8% ± 1.2% |
| o/u3.5:over | 6952 | 37.1% | 36.2% | +0.9% | -5.5% ± 1.6% |
| o/u3.5:under | 6952 | 62.9% | 63.8% | -0.9% | -8.4% ± 0.9% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 634 | 83.1% | 78.4% | +4.7% | -2.1% ± 1.8% |
| 1x2 @ 1.30–1.60 | 1498 | 67.6% | 63.6% | +4.0% | -1.8% ± 1.8% |
| 1x2 @ 1.60–2.00 | 2410 | 54.1% | 51.6% | +2.5% | -3.3% ± 1.8% |
| 1x2 @ 2.00–3.00 | 5858 | 38.8% | 37.8% | +1.0% | -5.8% ± 1.6% |
| 1x2 @ 3.00–5.00 | 10654 | 24.0% | 25.4% | -1.3% | -13.1% ± 1.5% |
| 1x2 @ 5.00–1000.00 | 3000 | 11.4% | 13.6% | -2.2% | -23.3% ± 4.2% |
| btts @ 1.00–1.30 | 112 | 72.3% | 73.2% | -0.9% | -10.2% ± 5.3% |
| btts @ 1.30–1.60 | 2883 | 61.4% | 61.5% | -0.2% | -8.9% ± 1.4% |
| btts @ 1.60–2.00 | 6247 | 51.4% | 51.4% | +0.1% | -8.5% ± 1.1% |
| btts @ 2.00–3.00 | 4319 | 40.5% | 40.6% | -0.1% | -8.4% ± 1.7% |
| btts @ 3.00–5.00 | 173 | 30.6% | 27.9% | +2.7% | +1.1% ± 11.7% |
| dc @ 1.00–1.30 | 10573 | 80.4% | 77.4% | +3.0% | -4.0% ± 0.5% |
| dc @ 1.30–1.60 | 7225 | 66.2% | 66.2% | +0.0% | -7.5% ± 0.8% |
| dc @ 1.60–2.00 | 2882 | 47.3% | 52.9% | -5.6% | -17.4% ± 1.6% |
| dc @ 2.00–3.00 | 1808 | 34.2% | 40.2% | -5.9% | -21.5% ± 2.6% |
| dc @ 3.00–5.00 | 483 | 15.9% | 26.3% | -10.3% | -43.3% ± 6.0% |
| dc @ 5.00–1000.00 | 48 | 4.2% | 16.5% | -12.3% | -78.1% ± 15.3% |
| o/u1.5 @ 1.00–1.30 | 4161 | 81.0% | 78.4% | +2.6% | -3.3% ± 0.7% |
| o/u1.5 @ 1.30–1.60 | 1844 | 69.6% | 67.2% | +2.3% | -3.8% ± 1.5% |
| o/u1.5 @ 1.60–2.00 | 134 | 60.4% | 54.4% | +6.0% | +3.1% ± 7.3% |
| o/u1.5 @ 2.00–3.00 | 1155 | 33.6% | 35.9% | -2.3% | -13.5% ± 3.6% |
| o/u1.5 @ 3.00–5.00 | 3855 | 22.2% | 24.8% | -2.5% | -16.2% ± 2.6% |
| o/u1.5 @ 5.00–1000.00 | 1087 | 12.8% | 15.9% | -3.1% | -24.0% ± 6.1% |
| o/u2.5 @ 1.00–1.30 | 283 | 79.5% | 75.6% | +4.0% | -1.7% ± 3.0% |
| o/u2.5 @ 1.30–1.60 | 3086 | 64.4% | 63.2% | +1.2% | -5.2% ± 1.3% |
| o/u2.5 @ 1.60–2.00 | 5952 | 53.0% | 52.3% | +0.7% | -5.8% ± 1.2% |
| o/u2.5 @ 2.00–3.00 | 5144 | 39.4% | 40.7% | -1.4% | -9.9% ± 1.6% |
| o/u2.5 @ 3.00–5.00 | 589 | 24.4% | 27.9% | -3.5% | -17.6% ± 6.0% |
| o/u3.5 @ 1.00–1.30 | 1551 | 76.1% | 75.7% | +0.4% | -6.8% ± 1.3% |
| o/u3.5 @ 1.30–1.60 | 3663 | 64.4% | 65.1% | -0.6% | -7.6% ± 1.1% |
| o/u3.5 @ 1.60–2.00 | 2312 | 53.8% | 53.0% | +0.8% | -5.3% ± 1.8% |
| o/u3.5 @ 2.00–3.00 | 3987 | 38.9% | 38.7% | +0.2% | -5.7% ± 1.9% |
| o/u3.5 @ 3.00–5.00 | 2280 | 26.4% | 26.6% | -0.2% | -7.8% ± 3.2% |
| o/u3.5 @ 5.00–1000.00 | 111 | 9.9% | 16.7% | -6.8% | -46.4% ± 15.4% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| England Amateur · Southern League Premier Central — o/u3.5:over | 58 | 53.4% | 36.3% | +17.1% | +35.0% ± 16.9% |
| Japan · J1 League — o/u2.5:over | 41 | 68.3% | 51.8% | +16.5% | +29.8% ± 14.5% |
| Simulated Reality League · Serie A SRL — o/u1.5:over | 37 | 91.9% | 75.3% | +16.5% | +15.2% ± 5.8% |
| Japan · J3 League — dc:12 | 40 | 90.0% | 72.8% | +17.2% | +14.5% ± 6.1% |
| Italy · Serie A — o/u1.5:over | 42 | 90.5% | 77.8% | +12.7% | +12.3% ± 5.9% |
| Sweden · Division 2 — dc:1x | 76 | 60.5% | 66.7% | -6.1% | -17.0% ± 8.1% |
| Spain · Primera Federacion — dc:12 | 53 | 64.2% | 71.4% | -7.2% | -17.7% ± 8.5% |
| England Amateur · National League South — dc:1x | 50 | 62.0% | 66.7% | -4.7% | -18.8% ± 9.3% |
| England · Championship — dc:1x | 55 | 61.8% | 70.0% | -8.2% | -18.9% ± 8.9% |
| USA · MLS — dc:12 | 72 | 65.3% | 76.0% | -10.7% | -18.9% ± 7.0% |
| Portugal · Campeonato de Portugal — dc:1x | 49 | 61.2% | 69.5% | -8.3% | -20.0% ± 9.5% |
| China · China League 2 — dc:12 | 39 | 61.5% | 70.6% | -9.0% | -20.8% ± 10.2% |
| Mexico · Liga MX — dc:12 | 34 | 61.8% | 74.9% | -13.1% | -21.8% ± 10.7% |
| England Amateur · Southern League Premier South — o/u3.5:under | 49 | 53.1% | 62.2% | -9.1% | -21.9% ± 10.6% |
| England · National League — dc:1x | 46 | 60.9% | 68.9% | -8.0% | -22.2% ± 9.5% |
| England Amateur · National League North — btts:yes | 52 | 50.0% | 58.6% | -8.6% | -22.3% ± 10.9% |
| Spain · Segunda Federacion — dc:12 | 106 | 61.3% | 71.7% | -10.4% | -22.4% ± 6.0% |
| Sweden · Division 2 — dc:x2 | 76 | 50.0% | 57.2% | -7.2% | -22.7% ± 9.3% |
| England Amateur · Southern League Premier South — dc:x2 | 50 | 50.0% | 58.1% | -8.1% | -23.7% ± 11.2% |
| Turkiye · 1. Lig — dc:1x | 44 | 56.8% | 67.8% | -11.0% | -24.5% ± 10.3% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 2862 | -0.0% | -6.9% |
| not covered | 1x2 | 21192 | +0.0% | -11.1% |
| covered | btts | 1904 | +0.0% | -5.5% |
| not covered | btts | 11830 | +0.0% | -8.9% |
| covered | dc | 2862 | -0.0% | -7.3% |
| not covered | dc | 20157 | -0.0% | -9.4% |
| covered | o/u1.5 | 1890 | +0.0% | -9.2% |
| not covered | o/u1.5 | 10346 | +0.0% | -10.3% |
| covered | o/u2.5 | 1908 | +0.0% | -5.5% |
| not covered | o/u2.5 | 13174 | +0.0% | -7.8% |
| covered | o/u3.5 | 1908 | +0.0% | -5.6% |
| not covered | o/u3.5 | 11996 | +0.0% | -7.1% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 16785 | 48.3% | 48.3% | +0.0% | +0.0% ± 1.0% |
| steady | 48802 | 54.8% | 54.3% | +0.5% | -7.8% ± 0.5% |
| drifted 3%+ | 22093 | 39.1% | 40.3% | -1.2% | -19.6% ± 0.8% |

## Basketball — 1660 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 1653 | 51.1% | 50.1% | +1.0% | -5.3% ± 2.3% |
| hcp:home | 1653 | 48.9% | 49.9% | -1.0% | -8.9% ± 2.3% |
| total:over | 1652 | 51.0% | 50.1% | +1.0% | -5.4% ± 2.3% |
| total:under | 1652 | 49.0% | 49.9% | -1.0% | -9.0% ± 2.3% |
| win:away | 1651 | 43.5% | 43.6% | -0.1% | -9.3% ± 3.2% |
| win:home | 1651 | 56.5% | 56.4% | +0.1% | -8.3% ± 2.5% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 3292 | 50.1% | 50.0% | +0.1% | -7.0% ± 1.6% |
| total @ 1.60–2.00 | 3303 | 50.0% | 50.0% | +0.0% | -7.2% ± 1.6% |
| win @ 1.00–1.30 | 662 | 82.8% | 82.3% | +0.5% | -6.6% ± 1.7% |
| win @ 1.30–1.60 | 565 | 64.8% | 66.0% | -1.2% | -8.4% ± 2.9% |
| win @ 1.60–2.00 | 552 | 50.2% | 53.1% | -2.9% | -11.0% ± 3.8% |
| win @ 2.00–3.00 | 684 | 43.7% | 39.6% | +4.1% | +3.3% ± 4.5% |
| win @ 3.00–5.00 | 483 | 27.1% | 25.8% | +1.4% | -0.9% ± 7.5% |
| win @ 5.00–1000.00 | 356 | 8.4% | 12.6% | -4.1% | -43.9% ± 10.1% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — total:over | 84 | 40.5% | 50.1% | -9.6% | -26.2% ± 9.8% |
| Italy · Serie A2 — hcp:away | 37 | 37.8% | 49.9% | -12.1% | -30.9% ± 14.8% |
| China · CBA — win:away | 40 | 35.0% | 41.0% | -6.0% | -36.9% ± 15.5% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 202 | +0.0% | -4.8% |
| not covered | hcp | 3104 | +0.0% | -7.3% |
| covered | total | 202 | +0.0% | -5.1% |
| not covered | total | 3102 | +0.0% | -7.3% |
| covered | win | 202 | +0.0% | -7.5% |
| not covered | win | 3100 | +0.0% | -8.9% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 1498 | 50.7% | 50.2% | +0.5% | +4.5% ± 3.2% |
| steady | 6101 | 51.8% | 51.7% | +0.1% | -6.9% ± 1.2% |
| drifted 3%+ | 1641 | 42.7% | 43.7% | -1.0% | -19.8% ± 2.6% |

