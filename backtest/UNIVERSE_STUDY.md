# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

7803 games graded (72% of 10801 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-27.

## Football — 6505 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 6425 | 31.3% | 32.1% | -0.8% | -14.0% ± 1.9% |
| 1x2:draw | 6425 | 23.8% | 24.7% | -0.9% | -12.7% ± 2.0% |
| 1x2:home | 6425 | 44.9% | 43.2% | +1.7% | -4.7% ± 1.6% |
| btts:no | 5468 | 43.9% | 45.8% | -1.9% | -11.9% ± 1.4% |
| btts:yes | 5468 | 56.1% | 54.2% | +1.9% | -5.0% ± 1.2% |
| dc:12 | 6116 | 76.3% | 74.5% | +1.9% | -5.3% ± 0.7% |
| dc:1x | 6116 | 68.6% | 67.7% | +0.9% | -7.9% ± 0.9% |
| dc:x2 | 6116 | 55.1% | 57.8% | -2.7% | -14.1% ± 1.1% |
| o/u1.5:over | 4853 | 76.9% | 74.5% | +2.4% | -3.5% ± 0.8% |
| o/u1.5:under | 4853 | 23.1% | 25.5% | -2.4% | -16.2% ± 2.3% |
| o/u2.5:over | 6040 | 56.2% | 53.9% | +2.3% | -3.0% ± 1.1% |
| o/u2.5:under | 6040 | 43.8% | 46.1% | -2.3% | -12.2% ± 1.3% |
| o/u3.5:over | 5520 | 37.2% | 36.1% | +1.1% | -5.0% ± 1.8% |
| o/u3.5:under | 5520 | 62.8% | 63.9% | -1.1% | -8.8% ± 1.0% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 497 | 82.9% | 78.1% | +4.8% | -2.0% ± 2.0% |
| 1x2 @ 1.30–1.60 | 1203 | 67.9% | 63.6% | +4.4% | -1.4% ± 2.0% |
| 1x2 @ 1.60–2.00 | 1929 | 53.7% | 51.6% | +2.1% | -4.0% ± 2.0% |
| 1x2 @ 2.00–3.00 | 4728 | 38.7% | 37.7% | +1.0% | -5.7% ± 1.7% |
| 1x2 @ 3.00–5.00 | 8541 | 24.1% | 25.4% | -1.3% | -12.8% ± 1.7% |
| 1x2 @ 5.00–1000.00 | 2377 | 11.3% | 13.6% | -2.3% | -23.2% ± 4.8% |
| btts @ 1.00–1.30 | 105 | 73.3% | 73.3% | +0.1% | -8.9% ± 5.4% |
| btts @ 1.30–1.60 | 2254 | 61.1% | 61.6% | -0.5% | -9.3% ± 1.5% |
| btts @ 1.60–2.00 | 5057 | 51.5% | 51.3% | +0.1% | -8.4% ± 1.3% |
| btts @ 2.00–3.00 | 3362 | 40.5% | 40.5% | -0.0% | -8.3% ± 1.9% |
| btts @ 3.00–5.00 | 158 | 30.4% | 27.9% | +2.5% | +0.7% ± 12.2% |
| dc @ 1.00–1.30 | 8393 | 80.4% | 77.3% | +3.0% | -4.0% ± 0.5% |
| dc @ 1.30–1.60 | 5818 | 66.0% | 66.2% | -0.2% | -7.9% ± 0.9% |
| dc @ 1.60–2.00 | 2285 | 48.0% | 52.9% | -4.9% | -16.1% ± 1.8% |
| dc @ 2.00–3.00 | 1441 | 34.2% | 40.1% | -5.9% | -21.5% ± 2.9% |
| dc @ 3.00–5.00 | 382 | 14.9% | 26.4% | -11.4% | -46.7% ± 6.6% |
| o/u1.5 @ 1.00–1.30 | 3229 | 80.9% | 78.4% | +2.5% | -3.4% ± 0.8% |
| o/u1.5 @ 1.30–1.60 | 1524 | 69.5% | 67.3% | +2.2% | -4.0% ± 1.6% |
| o/u1.5 @ 1.60–2.00 | 121 | 61.2% | 54.2% | +7.0% | +4.8% ± 7.7% |
| o/u1.5 @ 2.00–3.00 | 952 | 33.1% | 35.8% | -2.7% | -14.3% ± 4.0% |
| o/u1.5 @ 3.00–5.00 | 3039 | 22.4% | 24.9% | -2.4% | -15.6% ± 2.9% |
| o/u1.5 @ 5.00–1000.00 | 841 | 13.1% | 15.9% | -2.8% | -21.7% ± 7.1% |
| o/u2.5 @ 1.00–1.30 | 227 | 80.6% | 75.4% | +5.2% | -0.2% ± 3.3% |
| o/u2.5 @ 1.30–1.60 | 2430 | 64.4% | 63.3% | +1.2% | -5.2% ± 1.4% |
| o/u2.5 @ 1.60–2.00 | 4836 | 53.1% | 52.3% | +0.8% | -5.7% ± 1.3% |
| o/u2.5 @ 2.00–3.00 | 4081 | 39.3% | 40.8% | -1.4% | -10.2% ± 1.8% |
| o/u2.5 @ 3.00–5.00 | 486 | 23.7% | 27.9% | -4.3% | -20.1% ± 6.6% |
| o/u3.5 @ 1.00–1.30 | 1293 | 75.6% | 75.7% | -0.2% | -7.5% ± 1.5% |
| o/u3.5 @ 1.30–1.60 | 2858 | 64.8% | 65.1% | -0.3% | -7.1% ± 1.3% |
| o/u3.5 @ 1.60–2.00 | 1840 | 53.3% | 53.0% | +0.4% | -6.0% ± 2.1% |
| o/u3.5 @ 2.00–3.00 | 3091 | 39.0% | 38.6% | +0.4% | -5.3% ± 2.1% |
| o/u3.5 @ 3.00–5.00 | 1869 | 26.4% | 26.6% | -0.1% | -7.4% ± 3.6% |
| o/u3.5 @ 5.00–1000.00 | 89 | 9.0% | 16.5% | -7.6% | -50.4% ± 16.8% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · J3 League — dc:12 | 32 | 90.6% | 72.6% | +18.0% | +15.6% ± 6.7% |
| Portugal · Campeonato de Portugal — dc:1x | 47 | 61.7% | 69.7% | -8.0% | -19.5% ± 9.7% |
| England · Championship — dc:1x | 44 | 59.1% | 68.8% | -9.7% | -20.7% ± 10.3% |
| Spain · Segunda Federacion — dc:12 | 100 | 62.0% | 71.7% | -9.7% | -21.5% ± 6.2% |
| USA · MLS — dc:12 | 54 | 63.0% | 75.8% | -12.9% | -21.7% ± 8.3% |
| Sweden · Division 2 — dc:x2 | 75 | 49.3% | 57.3% | -8.0% | -24.0% ± 9.3% |
| China · China League 2 — dc:12 | 33 | 57.6% | 70.5% | -12.9% | -25.6% ± 11.3% |
| Portugal · Campeonato de Portugal — btts:no | 47 | 42.6% | 51.5% | -8.9% | -25.9% ± 12.7% |
| Sweden · Division 2 — btts:no | 68 | 30.9% | 36.8% | -5.9% | -27.0% ± 13.5% |
| Romania · Liga 3 — dc:x2 | 42 | 45.2% | 54.9% | -9.7% | -28.5% ± 13.3% |
| Turkiye · 1. Lig — dc:1x | 39 | 53.8% | 67.4% | -13.6% | -28.8% ± 10.9% |
| England · League One — dc:x2 | 44 | 45.5% | 56.6% | -11.1% | -30.5% ± 12.1% |
| Hungary · NB III — 1x2:away | 56 | 30.4% | 31.8% | -1.5% | -31.9% ± 15.5% |
| Sweden · Division 2 — o/u3.5:under | 68 | 39.7% | 53.4% | -13.7% | -33.3% ± 10.1% |
| International Clubs · UEFA Champions League — o/u3.5:under | 36 | 36.1% | 52.3% | -16.2% | -34.2% ± 14.9% |
| Turkiye · 1. Lig — 1x2:home | 39 | 33.3% | 41.5% | -8.2% | -34.8% ± 15.6% |
| Czechia · CFL — o/u3.5:under | 34 | 41.2% | 56.1% | -14.9% | -35.1% ± 13.6% |
| Portugal · Campeonato de Portugal — 1x2:home | 47 | 31.9% | 42.8% | -10.9% | -35.2% ± 14.6% |
| Sweden · Division 2 — o/u2.5:under | 67 | 23.9% | 34.6% | -10.7% | -35.7% ± 14.3% |
| Thailand · Thai League 2 — dc:x2 | 32 | 40.6% | 57.8% | -17.2% | -37.1% ± 14.0% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 2289 | -0.0% | -6.2% |
| not covered | 1x2 | 16986 | -0.0% | -11.1% |
| covered | btts | 1524 | +0.0% | -5.2% |
| not covered | btts | 9412 | +0.0% | -9.0% |
| covered | dc | 2289 | +0.0% | -7.1% |
| not covered | dc | 16059 | +0.0% | -9.4% |
| covered | o/u1.5 | 1516 | +0.0% | -7.6% |
| not covered | o/u1.5 | 8190 | +0.0% | -10.3% |
| covered | o/u2.5 | 1526 | +0.0% | -5.4% |
| not covered | o/u2.5 | 10554 | +0.0% | -7.9% |
| covered | o/u3.5 | 1526 | +0.0% | -5.7% |
| not covered | o/u3.5 | 9514 | +0.0% | -7.1% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 13429 | 48.8% | 48.4% | +0.4% | +0.9% ± 1.1% |
| steady | 39868 | 54.6% | 54.2% | +0.4% | -8.1% ± 0.5% |
| drifted 3%+ | 17707 | 39.0% | 40.3% | -1.2% | -19.7% ± 0.9% |

## Basketball — 1298 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 1292 | 50.3% | 50.1% | +0.2% | -6.7% ± 2.6% |
| hcp:home | 1292 | 49.7% | 49.9% | -0.2% | -7.6% ± 2.6% |
| total:over | 1292 | 50.8% | 50.1% | +0.7% | -5.9% ± 2.6% |
| total:under | 1292 | 49.2% | 49.9% | -0.7% | -8.6% ± 2.6% |
| win:away | 1291 | 42.2% | 43.0% | -0.8% | -11.7% ± 3.6% |
| win:home | 1291 | 57.8% | 57.0% | +0.8% | -6.8% ± 2.8% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 2575 | 50.1% | 50.0% | +0.1% | -7.1% ± 1.8% |
| total @ 1.60–2.00 | 2583 | 50.0% | 50.0% | +0.0% | -7.2% ± 1.8% |
| win @ 1.00–1.30 | 518 | 83.0% | 82.4% | +0.6% | -6.4% ± 1.9% |
| win @ 1.30–1.60 | 441 | 66.2% | 66.0% | +0.2% | -6.3% ± 3.2% |
| win @ 1.60–2.00 | 427 | 49.6% | 53.2% | -3.6% | -12.2% ± 4.3% |
| win @ 2.00–3.00 | 546 | 43.2% | 39.5% | +3.7% | +2.1% ± 5.1% |
| win @ 3.00–5.00 | 370 | 27.0% | 25.6% | +1.4% | -0.4% ± 8.6% |
| win @ 5.00–1000.00 | 280 | 7.5% | 12.5% | -5.0% | -48.9% ± 11.1% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — hcp:away | 64 | 42.2% | 50.1% | -7.9% | -23.5% ± 11.3% |
| Japan · B League One — total:over | 64 | 40.6% | 50.1% | -9.4% | -25.9% ± 11.3% |
| Japan · B League One — win:away | 64 | 35.9% | 46.0% | -10.0% | -33.1% ± 13.1% |
| Italy · Serie A2 — hcp:away | 34 | 35.3% | 49.9% | -14.6% | -35.6% ± 15.2% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 158 | +0.0% | -5.3% |
| not covered | hcp | 2426 | +0.0% | -7.3% |
| covered | total | 158 | +0.0% | -5.4% |
| not covered | total | 2426 | +0.0% | -7.3% |
| covered | win | 158 | +0.0% | -6.1% |
| not covered | win | 2424 | +0.0% | -9.5% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 1149 | 49.6% | 50.2% | -0.6% | +1.0% ± 3.6% |
| steady | 4787 | 52.0% | 51.7% | +0.2% | -6.8% ± 1.4% |
| drifted 3%+ | 1270 | 43.0% | 43.3% | -0.3% | -18.7% ± 3.0% |

