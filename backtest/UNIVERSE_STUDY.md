# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

8511 games graded (72% of 11895 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-30.

## Football — 7091 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 6951 | 32.0% | 32.4% | -0.4% | -12.5% ± 1.8% |
| 1x2:draw | 6951 | 23.3% | 24.6% | -1.3% | -14.5% ± 1.9% |
| 1x2:home | 6951 | 44.7% | 43.0% | +1.7% | -4.6% ± 1.6% |
| btts:no | 5949 | 44.4% | 45.8% | -1.4% | -11.0% ± 1.3% |
| btts:yes | 5949 | 55.6% | 54.2% | +1.4% | -5.7% ± 1.1% |
| dc:12 | 6634 | 76.9% | 74.6% | +2.3% | -4.8% ± 0.6% |
| dc:1x | 6634 | 67.9% | 67.5% | +0.4% | -8.8% ± 0.8% |
| dc:x2 | 6634 | 55.3% | 58.0% | -2.7% | -14.0% ± 1.0% |
| o/u1.5:over | 5312 | 76.9% | 74.6% | +2.2% | -3.8% ± 0.7% |
| o/u1.5:under | 5312 | 23.1% | 25.4% | -2.2% | -16.0% ± 2.2% |
| o/u2.5:over | 6549 | 56.2% | 54.1% | +2.1% | -3.4% ± 1.1% |
| o/u2.5:under | 6549 | 43.8% | 45.9% | -2.1% | -11.9% ± 1.3% |
| o/u3.5:over | 6007 | 37.1% | 36.2% | +0.9% | -5.7% ± 1.7% |
| o/u3.5:under | 6007 | 62.9% | 63.8% | -0.9% | -8.5% ± 0.9% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 573 | 83.6% | 78.5% | +5.1% | -1.6% ± 1.8% |
| 1x2 @ 1.30–1.60 | 1316 | 67.7% | 63.6% | +4.1% | -1.7% ± 1.9% |
| 1x2 @ 1.60–2.00 | 2064 | 54.3% | 51.6% | +2.7% | -3.0% ± 2.0% |
| 1x2 @ 2.00–3.00 | 5058 | 38.7% | 37.8% | +1.0% | -5.7% ± 1.7% |
| 1x2 @ 3.00–5.00 | 9161 | 24.0% | 25.4% | -1.4% | -13.4% ± 1.6% |
| 1x2 @ 5.00–1000.00 | 2681 | 11.5% | 13.5% | -2.1% | -22.2% ± 4.5% |
| btts @ 1.00–1.30 | 107 | 72.9% | 73.2% | -0.3% | -9.4% ± 5.4% |
| btts @ 1.30–1.60 | 2456 | 61.0% | 61.6% | -0.6% | -9.4% ± 1.5% |
| btts @ 1.60–2.00 | 5483 | 51.4% | 51.4% | +0.0% | -8.6% ± 1.2% |
| btts @ 2.00–3.00 | 3689 | 40.9% | 40.6% | +0.3% | -7.6% ± 1.8% |
| btts @ 3.00–5.00 | 163 | 30.7% | 27.9% | +2.8% | +1.3% ± 12.0% |
| dc @ 1.00–1.30 | 9146 | 80.7% | 77.5% | +3.2% | -3.7% ± 0.5% |
| dc @ 1.30–1.60 | 6234 | 66.0% | 66.2% | -0.2% | -7.9% ± 0.8% |
| dc @ 1.60–2.00 | 2460 | 47.4% | 52.9% | -5.4% | -17.1% ± 1.8% |
| dc @ 2.00–3.00 | 1582 | 34.3% | 40.1% | -5.8% | -21.3% ± 2.8% |
| dc @ 3.00–5.00 | 435 | 14.9% | 26.2% | -11.3% | -46.6% ± 6.2% |
| dc @ 5.00–1000.00 | 45 | 4.4% | 16.4% | -12.0% | -76.7% ± 16.3% |
| o/u1.5 @ 1.00–1.30 | 3577 | 80.9% | 78.5% | +2.4% | -3.5% ± 0.8% |
| o/u1.5 @ 1.30–1.60 | 1631 | 69.1% | 67.3% | +1.8% | -4.5% ± 1.6% |
| o/u1.5 @ 1.60–2.00 | 125 | 60.8% | 54.3% | +6.5% | +4.0% ± 7.5% |
| o/u1.5 @ 2.00–3.00 | 1017 | 33.6% | 35.8% | -2.2% | -13.1% ± 3.9% |
| o/u1.5 @ 3.00–5.00 | 3320 | 22.6% | 24.8% | -2.2% | -14.9% ± 2.8% |
| o/u1.5 @ 5.00–1000.00 | 954 | 12.9% | 15.8% | -2.9% | -23.6% ± 6.6% |
| o/u2.5 @ 1.00–1.30 | 260 | 80.0% | 75.6% | +4.4% | -1.2% ± 3.1% |
| o/u2.5 @ 1.30–1.60 | 2655 | 64.7% | 63.3% | +1.4% | -4.9% ± 1.4% |
| o/u2.5 @ 1.60–2.00 | 5178 | 53.2% | 52.3% | +0.9% | -5.6% ± 1.2% |
| o/u2.5 @ 2.00–3.00 | 4436 | 39.2% | 40.8% | -1.6% | -10.4% ± 1.7% |
| o/u2.5 @ 3.00–5.00 | 542 | 23.4% | 27.9% | -4.5% | -21.0% ± 6.2% |
| o/u3.5 @ 1.00–1.30 | 1382 | 76.5% | 75.7% | +0.8% | -6.3% ± 1.4% |
| o/u3.5 @ 1.30–1.60 | 3131 | 64.6% | 65.1% | -0.5% | -7.3% ± 1.2% |
| o/u3.5 @ 1.60–2.00 | 1992 | 53.6% | 53.0% | +0.6% | -5.6% ± 2.0% |
| o/u3.5 @ 2.00–3.00 | 3408 | 39.1% | 38.7% | +0.4% | -5.2% ± 2.0% |
| o/u3.5 @ 3.00–5.00 | 2006 | 25.8% | 26.6% | -0.7% | -9.7% ± 3.5% |
| o/u3.5 @ 5.00–1000.00 | 95 | 8.4% | 16.6% | -8.1% | -53.5% ± 15.8% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · J3 League — dc:12 | 32 | 90.6% | 72.6% | +18.0% | +15.6% ± 6.7% |
| Simulated Reality League · Serie A SRL — o/u1.5:over | 35 | 91.4% | 75.2% | +16.2% | +14.9% ± 6.2% |
| Portugal · Campeonato de Portugal — dc:1x | 47 | 61.7% | 69.7% | -8.0% | -19.5% ± 9.7% |
| England · Championship — dc:1x | 44 | 59.1% | 68.8% | -9.7% | -20.7% ± 10.3% |
| USA · MLS — dc:12 | 63 | 63.5% | 75.9% | -12.4% | -21.1% ± 7.6% |
| Spain · Segunda Federacion — dc:12 | 100 | 62.0% | 71.7% | -9.7% | -21.5% ± 6.2% |
| Italy · Serie B — dc:1x | 39 | 59.0% | 69.2% | -10.2% | -21.7% ± 10.8% |
| Sweden · Division 2 — dc:x2 | 75 | 49.3% | 57.3% | -8.0% | -24.0% ± 9.3% |
| China · China League 2 — dc:12 | 33 | 57.6% | 70.5% | -12.9% | -25.6% ± 11.3% |
| Portugal · Campeonato de Portugal — btts:no | 47 | 42.6% | 51.5% | -8.9% | -25.9% ± 12.7% |
| Sweden · Division 2 — btts:no | 68 | 30.9% | 36.8% | -5.9% | -27.0% ± 13.5% |
| Romania · Liga 3 — dc:x2 | 42 | 45.2% | 54.9% | -9.7% | -28.5% ± 13.3% |
| Saudi Arabia · Saudi Pro League — dc:1x | 31 | 54.8% | 64.0% | -9.1% | -28.6% ± 12.4% |
| Turkiye · 1. Lig — dc:1x | 39 | 53.8% | 67.4% | -13.6% | -28.8% ± 10.9% |
| Saudi Arabia · Saudi Pro League — o/u3.5:under | 31 | 45.2% | 60.6% | -15.4% | -29.6% ± 14.6% |
| England Amateur · Southern League Premier Central — btts:no | 47 | 34.0% | 43.5% | -9.4% | -29.9% ± 14.5% |
| England · National League — dc:1x | 34 | 55.9% | 68.6% | -12.7% | -30.3% ± 10.9% |
| Czechia · CFL — o/u3.5:under | 37 | 43.2% | 55.7% | -12.5% | -30.4% ± 13.4% |
| USA · MLS — 1x2:home | 63 | 34.9% | 46.0% | -11.1% | -30.6% ± 12.7% |
| Hungary · NB III — 1x2:away | 56 | 30.4% | 31.8% | -1.5% | -31.9% ± 15.5% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 2481 | -0.0% | -6.6% |
| not covered | 1x2 | 18372 | +0.0% | -11.1% |
| covered | btts | 1650 | +0.0% | -5.4% |
| not covered | btts | 10248 | +0.0% | -8.8% |
| covered | dc | 2481 | +0.0% | -7.2% |
| not covered | dc | 17421 | +0.0% | -9.5% |
| covered | o/u1.5 | 1642 | +0.0% | -8.2% |
| not covered | o/u1.5 | 8982 | +0.0% | -10.2% |
| covered | o/u2.5 | 1654 | +0.0% | -5.5% |
| not covered | o/u2.5 | 11444 | +0.0% | -7.9% |
| covered | o/u3.5 | 1654 | +0.0% | -5.9% |
| not covered | o/u3.5 | 10360 | +0.0% | -7.3% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 14507 | 48.8% | 48.3% | +0.5% | +1.0% ± 1.1% |
| steady | 42384 | 54.6% | 54.2% | +0.4% | -8.0% ± 0.5% |
| drifted 3%+ | 19065 | 38.9% | 40.2% | -1.3% | -19.8% ± 0.9% |

## Basketball — 1420 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 1413 | 50.2% | 50.1% | +0.1% | -6.9% ± 2.5% |
| hcp:home | 1413 | 49.8% | 49.9% | -0.1% | -7.3% ± 2.5% |
| total:over | 1413 | 50.7% | 50.1% | +0.6% | -6.0% ± 2.5% |
| total:under | 1413 | 49.3% | 49.9% | -0.6% | -8.3% ± 2.5% |
| win:away | 1412 | 42.4% | 43.4% | -1.0% | -11.9% ± 3.4% |
| win:home | 1412 | 57.6% | 56.6% | +1.0% | -5.9% ± 2.7% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 2815 | 50.1% | 50.0% | +0.1% | -6.9% ± 1.8% |
| total @ 1.60–2.00 | 2825 | 50.0% | 50.0% | +0.0% | -7.1% ± 1.7% |
| win @ 1.00–1.30 | 571 | 82.7% | 82.4% | +0.3% | -6.7% ± 1.8% |
| win @ 1.30–1.60 | 477 | 65.6% | 66.0% | -0.3% | -7.1% ± 3.1% |
| win @ 1.60–2.00 | 467 | 50.3% | 53.2% | -2.9% | -11.0% ± 4.1% |
| win @ 2.00–3.00 | 593 | 43.3% | 39.6% | +3.7% | +2.4% ± 4.9% |
| win @ 3.00–5.00 | 409 | 26.9% | 25.6% | +1.3% | -0.5% ± 8.2% |
| win @ 5.00–1000.00 | 307 | 8.1% | 12.6% | -4.5% | -45.5% ± 10.8% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| USA · NBA — win:home | 52 | 46.2% | 54.6% | -8.4% | -25.2% ± 12.0% |
| Japan · B League One — total:over | 67 | 40.3% | 50.0% | -9.7% | -26.4% ± 11.0% |
| International · Euroleague — hcp:home | 34 | 35.3% | 50.2% | -14.9% | -32.9% ± 15.8% |
| Italy · Serie A2 — hcp:away | 34 | 35.3% | 49.9% | -14.6% | -35.6% ± 15.2% |
| Japan · B League One — win:away | 67 | 34.3% | 45.9% | -11.6% | -36.1% ± 12.6% |
| China · CBA — win:away | 35 | 34.3% | 39.6% | -5.3% | -37.4% ± 16.7% |
| International · Euroleague — win:home | 34 | 44.1% | 60.8% | -16.7% | -37.7% ± 12.5% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 182 | +0.0% | -5.1% |
| not covered | hcp | 2644 | +0.0% | -7.2% |
| covered | total | 182 | +0.0% | -5.2% |
| not covered | total | 2644 | +0.0% | -7.3% |
| covered | win | 182 | +0.0% | -6.4% |
| not covered | win | 2642 | +0.0% | -9.1% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 1266 | 50.2% | 50.3% | -0.1% | +2.5% ± 3.4% |
| steady | 5213 | 51.9% | 51.7% | +0.2% | -6.8% ± 1.3% |
| drifted 3%+ | 1401 | 43.0% | 43.5% | -0.5% | -18.6% ± 2.8% |

