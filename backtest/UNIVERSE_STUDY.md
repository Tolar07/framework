# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

7679 games graded (73% of 10570 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-26.

## Football — 6413 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 6335 | 31.4% | 32.1% | -0.7% | -13.5% ± 1.9% |
| 1x2:draw | 6335 | 23.9% | 24.7% | -0.8% | -12.2% ± 2.0% |
| 1x2:home | 6335 | 44.7% | 43.2% | +1.5% | -5.2% ± 1.6% |
| btts:no | 5384 | 44.0% | 45.8% | -1.8% | -11.8% ± 1.4% |
| btts:yes | 5384 | 56.0% | 54.2% | +1.8% | -5.1% ± 1.2% |
| dc:12 | 6028 | 76.2% | 74.5% | +1.7% | -5.5% ± 0.7% |
| dc:1x | 6028 | 68.5% | 67.7% | +0.8% | -8.0% ± 0.9% |
| dc:x2 | 6028 | 55.4% | 57.8% | -2.5% | -13.6% ± 1.1% |
| o/u1.5:over | 4780 | 76.8% | 74.5% | +2.4% | -3.6% ± 0.8% |
| o/u1.5:under | 4780 | 23.2% | 25.5% | -2.4% | -15.9% ± 2.3% |
| o/u2.5:over | 5955 | 56.2% | 53.9% | +2.3% | -3.1% ± 1.2% |
| o/u2.5:under | 5955 | 43.8% | 46.1% | -2.3% | -12.1% ± 1.4% |
| o/u3.5:over | 5445 | 37.2% | 36.1% | +1.2% | -4.8% ± 1.8% |
| o/u3.5:under | 5445 | 62.8% | 63.9% | -1.2% | -8.9% ± 1.0% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 490 | 82.7% | 78.1% | +4.6% | -2.3% ± 2.0% |
| 1x2 @ 1.30–1.60 | 1189 | 67.6% | 63.5% | +4.1% | -1.8% ± 2.0% |
| 1x2 @ 1.60–2.00 | 1903 | 53.5% | 51.5% | +1.9% | -4.3% ± 2.1% |
| 1x2 @ 2.00–3.00 | 4655 | 38.6% | 37.7% | +0.9% | -5.9% ± 1.8% |
| 1x2 @ 3.00–5.00 | 8423 | 24.2% | 25.4% | -1.2% | -12.4% ± 1.7% |
| 1x2 @ 5.00–1000.00 | 2345 | 11.4% | 13.6% | -2.2% | -22.4% ± 4.8% |
| btts @ 1.00–1.30 | 103 | 73.8% | 73.2% | +0.6% | -8.3% ± 5.4% |
| btts @ 1.30–1.60 | 2223 | 61.1% | 61.6% | -0.5% | -9.2% ± 1.5% |
| btts @ 1.60–2.00 | 4978 | 51.5% | 51.3% | +0.2% | -8.4% ± 1.3% |
| btts @ 2.00–3.00 | 3309 | 40.5% | 40.5% | -0.0% | -8.4% ± 1.9% |
| btts @ 3.00–5.00 | 155 | 30.3% | 27.9% | +2.5% | +0.4% ± 12.3% |
| dc @ 1.00–1.30 | 8277 | 80.3% | 77.3% | +2.9% | -4.1% ± 0.5% |
| dc @ 1.30–1.60 | 5731 | 66.0% | 66.2% | -0.2% | -7.8% ± 0.9% |
| dc @ 1.60–2.00 | 2248 | 48.1% | 52.9% | -4.8% | -15.9% ± 1.8% |
| dc @ 2.00–3.00 | 1426 | 34.4% | 40.1% | -5.7% | -21.0% ± 2.9% |
| dc @ 3.00–5.00 | 373 | 15.3% | 26.4% | -11.1% | -45.4% ± 6.7% |
| o/u1.5 @ 1.00–1.30 | 3180 | 80.9% | 78.4% | +2.5% | -3.4% ± 0.8% |
| o/u1.5 @ 1.30–1.60 | 1505 | 69.4% | 67.4% | +2.1% | -4.1% ± 1.6% |
| o/u1.5 @ 1.60–2.00 | 116 | 60.3% | 54.1% | +6.3% | +3.6% ± 7.9% |
| o/u1.5 @ 2.00–3.00 | 935 | 33.2% | 35.7% | -2.6% | -14.0% ± 4.0% |
| o/u1.5 @ 3.00–5.00 | 2999 | 22.4% | 24.9% | -2.4% | -15.6% ± 2.9% |
| o/u1.5 @ 5.00–1000.00 | 825 | 13.3% | 15.9% | -2.6% | -20.2% ± 7.2% |
| o/u2.5 @ 1.00–1.30 | 223 | 80.3% | 75.4% | +4.9% | -0.6% ± 3.3% |
| o/u2.5 @ 1.30–1.60 | 2393 | 64.4% | 63.2% | +1.1% | -5.3% ± 1.4% |
| o/u2.5 @ 1.60–2.00 | 4776 | 53.1% | 52.3% | +0.8% | -5.8% ± 1.3% |
| o/u2.5 @ 2.00–3.00 | 4023 | 39.4% | 40.8% | -1.3% | -9.9% ± 1.8% |
| o/u2.5 @ 3.00–5.00 | 475 | 23.6% | 27.9% | -4.4% | -20.2% ± 6.7% |
| o/u3.5 @ 1.00–1.30 | 1278 | 75.5% | 75.7% | -0.2% | -7.5% ± 1.5% |
| o/u3.5 @ 1.30–1.60 | 2823 | 64.8% | 65.1% | -0.3% | -7.1% ± 1.3% |
| o/u3.5 @ 1.60–2.00 | 1806 | 53.3% | 53.0% | +0.4% | -6.0% ± 2.1% |
| o/u3.5 @ 2.00–3.00 | 3044 | 39.0% | 38.6% | +0.4% | -5.4% ± 2.2% |
| o/u3.5 @ 3.00–5.00 | 1851 | 26.5% | 26.6% | -0.0% | -7.1% ± 3.6% |
| o/u3.5 @ 5.00–1000.00 | 88 | 9.1% | 16.5% | -7.4% | -49.8% ± 17.0% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · J3 League — dc:12 | 32 | 90.6% | 72.6% | +18.0% | +15.6% ± 6.7% |
| Portugal · Campeonato de Portugal — dc:1x | 47 | 61.7% | 69.7% | -8.0% | -19.5% ± 9.7% |
| England · Championship — dc:1x | 44 | 59.1% | 68.8% | -9.7% | -20.7% ± 10.3% |
| Spain · Segunda Federacion — dc:12 | 100 | 62.0% | 71.7% | -9.7% | -21.5% ± 6.2% |
| USA · MLS — dc:12 | 54 | 63.0% | 75.8% | -12.9% | -21.7% ± 8.3% |
| Sweden · Division 2 — dc:x2 | 75 | 49.3% | 57.3% | -8.0% | -24.0% ± 9.3% |
| Portugal · Campeonato de Portugal — btts:no | 47 | 42.6% | 51.5% | -8.9% | -25.9% ± 12.7% |
| Sweden · Division 2 — btts:no | 68 | 30.9% | 36.8% | -5.9% | -27.0% ± 13.5% |
| China · China League 2 — dc:12 | 32 | 56.2% | 70.4% | -14.1% | -27.2% ± 11.6% |
| Romania · Liga 3 — dc:x2 | 42 | 45.2% | 54.9% | -9.7% | -28.5% ± 13.3% |
| Turkiye · 1. Lig — dc:1x | 38 | 52.6% | 67.1% | -14.4% | -30.0% ± 11.2% |
| England · League One — dc:x2 | 44 | 45.5% | 56.6% | -11.1% | -30.5% ± 12.1% |
| Hungary · NB III — 1x2:away | 56 | 30.4% | 31.8% | -1.5% | -31.9% ± 15.5% |
| Sweden · Division 2 — o/u3.5:under | 68 | 39.7% | 53.4% | -13.7% | -33.3% ± 10.1% |
| International Clubs · UEFA Champions League — o/u3.5:under | 36 | 36.1% | 52.3% | -16.2% | -34.2% ± 14.9% |
| Czechia · CFL — o/u3.5:under | 34 | 41.2% | 56.1% | -14.9% | -35.1% ± 13.6% |
| Thailand · Thai League 2 — dc:x2 | 31 | 41.9% | 58.1% | -16.2% | -35.1% ± 14.3% |
| Portugal · Campeonato de Portugal — 1x2:home | 47 | 31.9% | 42.8% | -10.9% | -35.2% ± 14.6% |
| Sweden · Division 2 — o/u2.5:under | 67 | 23.9% | 34.6% | -10.7% | -35.7% ± 14.3% |
| Turkiye · 1. Lig — 1x2:home | 38 | 31.6% | 41.1% | -9.5% | -37.4% ± 15.8% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 2253 | -0.0% | -6.0% |
| not covered | 1x2 | 16752 | -0.0% | -10.9% |
| covered | btts | 1500 | +0.0% | -5.1% |
| not covered | btts | 9268 | +0.0% | -9.0% |
| covered | dc | 2253 | +0.0% | -7.0% |
| not covered | dc | 15831 | +0.0% | -9.3% |
| covered | o/u1.5 | 1492 | +0.0% | -7.1% |
| not covered | o/u1.5 | 8068 | +0.0% | -10.2% |
| covered | o/u2.5 | 1502 | +0.0% | -5.4% |
| not covered | o/u2.5 | 10408 | +0.0% | -7.9% |
| covered | o/u3.5 | 1502 | +0.0% | -5.7% |
| not covered | o/u3.5 | 9388 | +0.0% | -7.0% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 13211 | 48.8% | 48.4% | +0.4% | +0.8% ± 1.1% |
| steady | 39338 | 54.6% | 54.2% | +0.4% | -8.1% ± 0.5% |
| drifted 3%+ | 17427 | 39.1% | 40.3% | -1.1% | -19.4% ± 0.9% |

## Basketball — 1266 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 1261 | 50.0% | 50.1% | -0.0% | -7.2% ± 2.6% |
| hcp:home | 1261 | 50.0% | 49.9% | +0.0% | -7.1% ± 2.6% |
| total:over | 1260 | 50.9% | 50.1% | +0.8% | -5.7% ± 2.6% |
| total:under | 1260 | 49.1% | 49.9% | -0.8% | -8.8% ± 2.6% |
| win:away | 1259 | 41.8% | 42.7% | -1.0% | -12.3% ± 3.7% |
| win:home | 1259 | 58.2% | 57.3% | +1.0% | -6.3% ± 2.8% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 2513 | 50.1% | 50.0% | +0.1% | -7.1% ± 1.9% |
| total @ 1.60–2.00 | 2519 | 50.0% | 50.0% | +0.0% | -7.2% ± 1.8% |
| win @ 1.00–1.30 | 508 | 83.3% | 82.5% | +0.8% | -6.1% ± 1.9% |
| win @ 1.30–1.60 | 425 | 65.6% | 66.0% | -0.4% | -7.3% ± 3.3% |
| win @ 1.60–2.00 | 419 | 49.6% | 53.2% | -3.6% | -12.2% ± 4.3% |
| win @ 2.00–3.00 | 530 | 43.8% | 39.6% | +4.2% | +3.3% ± 5.2% |
| win @ 3.00–5.00 | 360 | 26.7% | 25.6% | +1.0% | -1.7% ± 8.7% |
| win @ 5.00–1000.00 | 276 | 7.6% | 12.5% | -4.9% | -48.2% ± 11.3% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — hcp:away | 64 | 42.2% | 50.1% | -7.9% | -23.5% ± 11.3% |
| Japan · B League One — total:over | 64 | 40.6% | 50.1% | -9.4% | -25.9% ± 11.3% |
| USA · NBA — win:home | 35 | 45.7% | 55.5% | -9.8% | -28.7% ± 13.9% |
| Japan · B League One — win:away | 64 | 35.9% | 46.0% | -10.0% | -33.1% ± 13.1% |
| Italy · Serie A2 — hcp:away | 34 | 35.3% | 49.9% | -14.6% | -35.6% ± 15.2% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 148 | +0.0% | -5.4% |
| not covered | hcp | 2374 | +0.0% | -7.3% |
| covered | total | 148 | +0.0% | -5.4% |
| not covered | total | 2372 | +0.0% | -7.3% |
| covered | win | 148 | +0.0% | -6.8% |
| not covered | win | 2370 | +0.0% | -9.5% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 1118 | 50.4% | 50.2% | +0.1% | +2.4% ± 3.6% |
| steady | 4677 | 51.9% | 51.7% | +0.2% | -6.9% ± 1.4% |
| drifted 3%+ | 1231 | 42.4% | 43.2% | -0.8% | -19.6% ± 3.0% |

