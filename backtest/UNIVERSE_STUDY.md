# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

10384 games graded (71% of 14635 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-11-02.

## Football — 8656 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 8509 | 31.5% | 32.3% | -0.8% | -13.8% ± 1.7% |
| 1x2:draw | 8509 | 23.5% | 24.7% | -1.1% | -13.8% ± 1.7% |
| 1x2:home | 8509 | 45.0% | 43.1% | +1.9% | -4.3% ± 1.5% |
| btts:no | 7246 | 44.3% | 45.8% | -1.5% | -11.2% ± 1.2% |
| btts:yes | 7246 | 55.7% | 54.2% | +1.5% | -5.6% ± 1.0% |
| dc:12 | 8091 | 76.5% | 74.5% | +2.0% | -5.1% ± 0.6% |
| dc:1x | 8091 | 68.3% | 67.6% | +0.8% | -8.2% ± 0.7% |
| dc:x2 | 8091 | 55.1% | 58.0% | -2.8% | -14.2% ± 0.9% |
| o/u1.5:over | 6478 | 77.1% | 74.6% | +2.5% | -3.5% ± 0.7% |
| o/u1.5:under | 6478 | 22.9% | 25.4% | -2.5% | -17.0% ± 2.0% |
| o/u2.5:over | 8019 | 56.0% | 53.9% | +2.0% | -3.5% ± 1.0% |
| o/u2.5:under | 8019 | 44.0% | 46.1% | -2.0% | -11.5% ± 1.2% |
| o/u3.5:over | 7319 | 36.7% | 36.1% | +0.6% | -6.4% ± 1.5% |
| o/u3.5:under | 7319 | 63.3% | 63.9% | -0.6% | -8.0% ± 0.8% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 670 | 83.1% | 78.4% | +4.8% | -2.0% ± 1.7% |
| 1x2 @ 1.30–1.60 | 1575 | 67.8% | 63.6% | +4.2% | -1.5% ± 1.7% |
| 1x2 @ 1.60–2.00 | 2566 | 54.2% | 51.6% | +2.6% | -3.2% ± 1.8% |
| 1x2 @ 2.00–3.00 | 6214 | 38.9% | 37.8% | +1.1% | -5.6% ± 1.5% |
| 1x2 @ 3.00–5.00 | 11333 | 24.0% | 25.4% | -1.4% | -13.3% ± 1.5% |
| 1x2 @ 5.00–1000.00 | 3169 | 11.3% | 13.6% | -2.3% | -23.2% ± 4.2% |
| btts @ 1.00–1.30 | 116 | 70.7% | 73.3% | -2.6% | -12.1% ± 5.3% |
| btts @ 1.30–1.60 | 3002 | 61.5% | 61.5% | -0.1% | -8.7% ± 1.3% |
| btts @ 1.60–2.00 | 6679 | 51.3% | 51.4% | -0.1% | -8.7% ± 1.1% |
| btts @ 2.00–3.00 | 4515 | 40.7% | 40.6% | +0.1% | -8.1% ± 1.7% |
| btts @ 3.00–5.00 | 180 | 31.7% | 27.9% | +3.7% | +4.8% ± 11.6% |
| dc @ 1.00–1.30 | 11150 | 80.5% | 77.4% | +3.1% | -3.9% ± 0.5% |
| dc @ 1.30–1.60 | 7610 | 66.2% | 66.2% | -0.0% | -7.6% ± 0.8% |
| dc @ 1.60–2.00 | 3053 | 47.2% | 52.9% | -5.7% | -17.5% ± 1.6% |
| dc @ 2.00–3.00 | 1898 | 34.1% | 40.2% | -6.0% | -21.8% ± 2.5% |
| dc @ 3.00–5.00 | 512 | 15.8% | 26.3% | -10.5% | -44.0% ± 5.8% |
| dc @ 5.00–1000.00 | 50 | 4.0% | 16.5% | -12.5% | -79.0% ± 14.7% |
| o/u1.5 @ 1.00–1.30 | 4370 | 81.1% | 78.4% | +2.7% | -3.2% ± 0.7% |
| o/u1.5 @ 1.30–1.60 | 1987 | 69.4% | 67.2% | +2.2% | -4.1% ± 1.4% |
| o/u1.5 @ 1.60–2.00 | 145 | 60.0% | 54.3% | +5.7% | +2.7% ± 7.0% |
| o/u1.5 @ 2.00–3.00 | 1247 | 34.1% | 35.8% | -1.7% | -12.0% ± 3.5% |
| o/u1.5 @ 3.00–5.00 | 4063 | 22.2% | 24.8% | -2.7% | -16.5% ± 2.5% |
| o/u1.5 @ 5.00–1000.00 | 1144 | 12.6% | 15.9% | -3.3% | -25.3% ± 5.9% |
| o/u2.5 @ 1.00–1.30 | 298 | 80.5% | 75.5% | +5.0% | -0.3% ± 2.9% |
| o/u2.5 @ 1.30–1.60 | 3230 | 64.5% | 63.2% | +1.3% | -5.0% ± 1.2% |
| o/u2.5 @ 1.60–2.00 | 6432 | 53.1% | 52.3% | +0.8% | -5.7% ± 1.1% |
| o/u2.5 @ 2.00–3.00 | 5428 | 39.2% | 40.8% | -1.6% | -10.3% ± 1.5% |
| o/u2.5 @ 3.00–5.00 | 622 | 24.3% | 27.9% | -3.6% | -18.4% ± 5.8% |
| o/u3.5 @ 1.00–1.30 | 1679 | 76.5% | 75.7% | +0.8% | -6.3% ± 1.3% |
| o/u3.5 @ 1.30–1.60 | 3832 | 64.8% | 65.1% | -0.3% | -7.2% ± 1.1% |
| o/u3.5 @ 1.60–2.00 | 2402 | 53.9% | 53.1% | +0.9% | -5.2% ± 1.8% |
| o/u3.5 @ 2.00–3.00 | 4156 | 38.8% | 38.7% | +0.1% | -6.1% ± 1.8% |
| o/u3.5 @ 3.00–5.00 | 2455 | 25.8% | 26.6% | -0.8% | -10.0% ± 3.1% |
| o/u3.5 @ 5.00–1000.00 | 114 | 10.5% | 16.8% | -6.2% | -43.2% ± 15.6% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| England Amateur · Southern League Premier Central — o/u3.5:over | 58 | 53.4% | 36.3% | +17.1% | +35.0% ± 16.9% |
| Japan · J1 League — o/u2.5:over | 44 | 70.5% | 51.6% | +18.8% | +34.6% ± 13.8% |
| Turkiye Amateur · 2. Lig — o/u2.5:over | 30 | 76.7% | 55.6% | +21.1% | +26.7% ± 13.2% |
| Simulated Reality League · Serie A SRL — o/u1.5:over | 37 | 91.9% | 75.3% | +16.5% | +15.2% ± 5.8% |
| Spain · Primera Federacion — dc:1x | 57 | 86.0% | 69.1% | +16.8% | +15.1% ± 6.5% |
| Japan · J3 League — dc:12 | 40 | 90.0% | 72.8% | +17.2% | +14.5% ± 6.1% |
| Japan · J1 League — o/u1.5:over | 44 | 88.6% | 74.8% | +13.8% | +14.2% ± 6.4% |
| Germany · 3. Liga — o/u1.5:over | 31 | 96.8% | 81.9% | +14.9% | +11.5% ± 3.8% |
| USA · MLS — dc:12 | 77 | 67.5% | 76.1% | -8.6% | -16.2% ± 6.7% |
| Sweden · Division 2 — dc:1x | 77 | 61.0% | 66.7% | -5.7% | -16.3% ± 8.0% |
| Spain · Primera Federacion — dc:12 | 57 | 64.9% | 71.4% | -6.5% | -16.7% ± 8.2% |
| England Amateur · National League South — dc:1x | 50 | 62.0% | 66.7% | -4.7% | -18.8% ± 9.3% |
| England · Championship — dc:1x | 55 | 61.8% | 70.0% | -8.2% | -18.9% ± 8.9% |
| China · China League 2 — dc:12 | 39 | 61.5% | 70.6% | -9.0% | -20.8% ± 10.2% |
| Spain · Segunda Federacion — dc:12 | 122 | 62.3% | 71.7% | -9.4% | -21.0% ± 5.6% |
| Sweden · Allsvenskan — o/u1.5:over | 35 | 65.7% | 78.9% | -13.2% | -21.4% ± 9.8% |
| England Amateur · Southern League Premier South — o/u3.5:under | 49 | 53.1% | 62.2% | -9.1% | -21.9% ± 10.6% |
| England · National League — dc:1x | 46 | 60.9% | 68.9% | -8.0% | -22.2% ± 9.5% |
| England Amateur · National League North — btts:yes | 52 | 50.0% | 58.6% | -8.6% | -22.3% ± 10.9% |
| Sweden · Division 2 — dc:x2 | 77 | 49.4% | 57.3% | -7.9% | -23.7% ± 9.2% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 3054 | -0.0% | -7.3% |
| not covered | 1x2 | 22473 | +0.0% | -11.1% |
| covered | btts | 2032 | +0.0% | -5.4% |
| not covered | btts | 12460 | +0.0% | -8.9% |
| covered | dc | 3054 | -0.0% | -7.5% |
| not covered | dc | 21219 | +0.0% | -9.4% |
| covered | o/u1.5 | 2018 | +0.0% | -9.1% |
| not covered | o/u1.5 | 10938 | +0.0% | -10.5% |
| covered | o/u2.5 | 2036 | +0.0% | -5.4% |
| not covered | o/u2.5 | 14002 | +0.0% | -7.8% |
| covered | o/u3.5 | 2036 | +0.0% | -5.8% |
| not covered | o/u3.5 | 12602 | +0.0% | -7.4% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 17160 | 48.4% | 48.2% | +0.2% | +0.2% ± 1.0% |
| steady | 53637 | 54.4% | 54.0% | +0.5% | -8.0% ± 0.4% |
| drifted 3%+ | 22551 | 39.0% | 40.2% | -1.2% | -19.7% ± 0.8% |

## Basketball — 1728 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 1720 | 51.3% | 50.1% | +1.2% | -4.9% ± 2.2% |
| hcp:home | 1720 | 48.7% | 49.9% | -1.2% | -9.4% ± 2.2% |
| total:over | 1719 | 51.1% | 50.1% | +1.0% | -5.3% ± 2.2% |
| total:under | 1719 | 48.9% | 49.9% | -1.0% | -9.1% ± 2.2% |
| win:away | 1718 | 43.5% | 43.6% | -0.1% | -9.7% ± 3.1% |
| win:home | 1718 | 56.5% | 56.4% | +0.1% | -8.2% ± 2.4% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 3425 | 50.1% | 50.0% | +0.1% | -7.0% ± 1.6% |
| total @ 1.60–2.00 | 3437 | 50.0% | 50.0% | +0.0% | -7.2% ± 1.6% |
| win @ 1.00–1.30 | 693 | 82.8% | 82.3% | +0.5% | -6.5% ± 1.6% |
| win @ 1.30–1.60 | 580 | 64.8% | 65.9% | -1.1% | -8.3% ± 2.8% |
| win @ 1.60–2.00 | 580 | 50.0% | 53.1% | -3.1% | -11.4% ± 3.7% |
| win @ 2.00–3.00 | 708 | 43.9% | 39.7% | +4.3% | +3.6% ± 4.5% |
| win @ 3.00–5.00 | 503 | 27.2% | 25.8% | +1.5% | -0.4% ± 7.4% |
| win @ 5.00–1000.00 | 372 | 8.1% | 12.6% | -4.5% | -46.3% ± 9.7% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — total:over | 84 | 40.5% | 50.1% | -9.6% | -26.2% ± 9.8% |
| Italy · Serie A2 — hcp:away | 42 | 38.1% | 50.0% | -11.9% | -30.7% ± 13.8% |
| China · CBA — win:away | 43 | 34.9% | 39.7% | -4.8% | -36.2% ± 15.0% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 204 | +0.0% | -4.9% |
| not covered | hcp | 3236 | +0.0% | -7.3% |
| covered | total | 204 | +0.0% | -5.0% |
| not covered | total | 3234 | +0.0% | -7.3% |
| covered | win | 204 | +0.0% | -7.6% |
| not covered | win | 3232 | +0.0% | -9.0% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 1525 | 50.5% | 50.1% | +0.4% | +4.0% ± 3.1% |
| steady | 6419 | 51.8% | 51.6% | +0.2% | -6.9% ± 1.2% |
| drifted 3%+ | 1672 | 42.8% | 43.7% | -1.0% | -19.6% ± 2.5% |

