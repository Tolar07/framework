# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

8368 games graded (72% of 11642 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-29.

## Football — 6976 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 6848 | 31.9% | 32.3% | -0.4% | -12.3% ± 1.9% |
| 1x2:draw | 6848 | 23.3% | 24.6% | -1.2% | -14.2% ± 1.9% |
| 1x2:home | 6848 | 44.7% | 43.1% | +1.6% | -4.9% ± 1.6% |
| btts:no | 5853 | 44.3% | 45.8% | -1.5% | -11.2% ± 1.3% |
| btts:yes | 5853 | 55.7% | 54.2% | +1.5% | -5.5% ± 1.1% |
| dc:12 | 6533 | 76.8% | 74.6% | +2.2% | -4.9% ± 0.7% |
| dc:1x | 6533 | 67.9% | 67.6% | +0.4% | -8.7% ± 0.8% |
| dc:x2 | 6533 | 55.3% | 57.9% | -2.6% | -13.9% ± 1.0% |
| o/u1.5:over | 5213 | 77.0% | 74.6% | +2.4% | -3.6% ± 0.7% |
| o/u1.5:under | 5213 | 23.0% | 25.4% | -2.4% | -16.3% ± 2.2% |
| o/u2.5:over | 6448 | 56.3% | 54.1% | +2.2% | -3.2% ± 1.1% |
| o/u2.5:under | 6448 | 43.7% | 45.9% | -2.2% | -12.0% ± 1.3% |
| o/u3.5:over | 5911 | 37.2% | 36.2% | +1.0% | -5.4% ± 1.7% |
| o/u3.5:under | 5911 | 62.8% | 63.8% | -1.0% | -8.6% ± 0.9% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 559 | 83.2% | 78.4% | +4.8% | -2.0% ± 1.9% |
| 1x2 @ 1.30–1.60 | 1291 | 67.7% | 63.6% | +4.1% | -1.8% ± 1.9% |
| 1x2 @ 1.60–2.00 | 2040 | 54.1% | 51.6% | +2.5% | -3.4% ± 2.0% |
| 1x2 @ 2.00–3.00 | 4994 | 38.7% | 37.8% | +0.9% | -5.7% ± 1.7% |
| 1x2 @ 3.00–5.00 | 9039 | 24.0% | 25.4% | -1.4% | -13.2% ± 1.6% |
| 1x2 @ 5.00–1000.00 | 2621 | 11.5% | 13.5% | -2.0% | -21.7% ± 4.6% |
| btts @ 1.00–1.30 | 107 | 72.9% | 73.2% | -0.3% | -9.4% ± 5.4% |
| btts @ 1.30–1.60 | 2420 | 61.0% | 61.6% | -0.5% | -9.3% ± 1.5% |
| btts @ 1.60–2.00 | 5382 | 51.4% | 51.4% | +0.1% | -8.5% ± 1.2% |
| btts @ 2.00–3.00 | 3636 | 40.7% | 40.6% | +0.2% | -7.9% ± 1.9% |
| btts @ 3.00–5.00 | 161 | 30.4% | 27.9% | +2.6% | +0.7% ± 12.1% |
| dc @ 1.00–1.30 | 9004 | 80.6% | 77.4% | +3.2% | -3.8% ± 0.5% |
| dc @ 1.30–1.60 | 6146 | 65.9% | 66.2% | -0.3% | -7.9% ± 0.8% |
| dc @ 1.60–2.00 | 2429 | 47.7% | 52.9% | -5.1% | -16.6% ± 1.8% |
| dc @ 2.00–3.00 | 1553 | 34.2% | 40.1% | -5.9% | -21.6% ± 2.8% |
| dc @ 3.00–5.00 | 426 | 15.3% | 26.2% | -10.9% | -45.5% ± 6.3% |
| dc @ 5.00–1000.00 | 41 | 4.9% | 16.6% | -11.8% | -74.4% ± 17.9% |
| o/u1.5 @ 1.00–1.30 | 3512 | 81.0% | 78.5% | +2.5% | -3.4% ± 0.8% |
| o/u1.5 @ 1.30–1.60 | 1600 | 69.2% | 67.3% | +1.9% | -4.3% ± 1.6% |
| o/u1.5 @ 1.60–2.00 | 122 | 60.7% | 54.2% | +6.5% | +3.9% ± 7.7% |
| o/u1.5 @ 2.00–3.00 | 994 | 33.5% | 35.8% | -2.3% | -13.4% ± 3.9% |
| o/u1.5 @ 3.00–5.00 | 3268 | 22.5% | 24.8% | -2.3% | -15.3% ± 2.8% |
| o/u1.5 @ 5.00–1000.00 | 930 | 12.8% | 15.8% | -3.0% | -23.9% ± 6.7% |
| o/u2.5 @ 1.00–1.30 | 254 | 80.3% | 75.5% | +4.9% | -0.6% ± 3.1% |
| o/u2.5 @ 1.30–1.60 | 2611 | 64.7% | 63.3% | +1.5% | -4.8% ± 1.4% |
| o/u2.5 @ 1.60–2.00 | 5108 | 53.1% | 52.3% | +0.8% | -5.8% ± 1.2% |
| o/u2.5 @ 2.00–3.00 | 4364 | 39.3% | 40.8% | -1.5% | -10.2% ± 1.7% |
| o/u2.5 @ 3.00–5.00 | 536 | 23.3% | 27.9% | -4.6% | -21.3% ± 6.2% |
| o/u3.5 @ 1.00–1.30 | 1356 | 76.3% | 75.7% | +0.5% | -6.6% ± 1.4% |
| o/u3.5 @ 1.30–1.60 | 3081 | 64.6% | 65.1% | -0.5% | -7.3% ± 1.2% |
| o/u3.5 @ 1.60–2.00 | 1968 | 53.6% | 53.0% | +0.6% | -5.7% ± 2.0% |
| o/u3.5 @ 2.00–3.00 | 3358 | 39.1% | 38.7% | +0.4% | -5.2% ± 2.1% |
| o/u3.5 @ 3.00–5.00 | 1967 | 26.0% | 26.6% | -0.6% | -9.1% ± 3.5% |
| o/u3.5 @ 5.00–1000.00 | 92 | 8.7% | 16.6% | -7.9% | -52.0% ± 16.3% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · J3 League — dc:12 | 32 | 90.6% | 72.6% | +18.0% | +15.6% ± 6.7% |
| Simulated Reality League · Serie A SRL — o/u1.5:over | 33 | 90.9% | 75.0% | +15.9% | +14.6% ± 6.6% |
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
| Turkiye · 1. Lig — dc:1x | 39 | 53.8% | 67.4% | -13.6% | -28.8% ± 10.9% |
| England Amateur · Southern League Premier Central — btts:no | 47 | 34.0% | 43.5% | -9.4% | -29.9% ± 14.5% |
| England · National League — dc:1x | 34 | 55.9% | 68.6% | -12.7% | -30.3% ± 10.9% |
| Czechia · CFL — o/u3.5:under | 37 | 43.2% | 55.7% | -12.5% | -30.4% ± 13.4% |
| USA · MLS — 1x2:home | 63 | 34.9% | 46.0% | -11.1% | -30.6% ± 12.7% |
| Hungary · NB III — 1x2:away | 56 | 30.4% | 31.8% | -1.5% | -31.9% ± 15.5% |
| England · League One — dc:x2 | 48 | 43.8% | 56.0% | -12.3% | -32.7% ± 11.5% |
| Sweden · Division 2 — o/u3.5:under | 68 | 39.7% | 53.4% | -13.7% | -33.3% ± 10.1% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 2457 | -0.0% | -6.5% |
| not covered | 1x2 | 18087 | +0.0% | -11.0% |
| covered | btts | 1634 | +0.0% | -5.3% |
| not covered | btts | 10072 | +0.0% | -8.8% |
| covered | dc | 2457 | +0.0% | -7.2% |
| not covered | dc | 17142 | +0.0% | -9.4% |
| covered | o/u1.5 | 1626 | +0.0% | -8.2% |
| not covered | o/u1.5 | 8800 | +0.0% | -10.3% |
| covered | o/u2.5 | 1638 | +0.0% | -5.5% |
| not covered | o/u2.5 | 11258 | +0.0% | -7.9% |
| covered | o/u3.5 | 1638 | +0.0% | -5.8% |
| not covered | o/u3.5 | 10184 | +0.0% | -7.2% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 14239 | 48.8% | 48.4% | +0.4% | +1.0% ± 1.1% |
| steady | 41977 | 54.6% | 54.2% | +0.4% | -8.0% ± 0.5% |
| drifted 3%+ | 18783 | 38.9% | 40.1% | -1.2% | -19.7% ± 0.9% |

## Basketball — 1392 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 1385 | 50.2% | 50.1% | +0.1% | -6.9% ± 2.5% |
| hcp:home | 1385 | 49.8% | 49.9% | -0.1% | -7.3% ± 2.5% |
| total:over | 1385 | 50.4% | 50.1% | +0.3% | -6.5% ± 2.5% |
| total:under | 1385 | 49.6% | 49.9% | -0.3% | -7.8% ± 2.5% |
| win:away | 1384 | 42.5% | 43.4% | -0.9% | -11.4% ± 3.5% |
| win:home | 1384 | 57.5% | 56.6% | +0.9% | -6.1% ± 2.7% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 2759 | 50.1% | 50.0% | +0.1% | -6.9% ± 1.8% |
| total @ 1.60–2.00 | 2769 | 50.0% | 50.0% | +0.0% | -7.1% ± 1.8% |
| win @ 1.00–1.30 | 560 | 82.5% | 82.4% | +0.1% | -6.9% ± 1.8% |
| win @ 1.30–1.60 | 468 | 65.6% | 65.9% | -0.3% | -7.2% ± 3.1% |
| win @ 1.60–2.00 | 454 | 50.2% | 53.3% | -3.1% | -11.2% ± 4.2% |
| win @ 2.00–3.00 | 586 | 43.3% | 39.6% | +3.7% | +2.4% ± 4.9% |
| win @ 3.00–5.00 | 397 | 27.2% | 25.6% | +1.6% | +0.5% ± 8.4% |
| win @ 5.00–1000.00 | 303 | 8.3% | 12.6% | -4.4% | -44.8% ± 10.9% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — hcp:away | 65 | 41.5% | 50.1% | -8.5% | -24.7% ± 11.2% |
| Japan · B League One — total:over | 65 | 40.0% | 50.0% | -10.0% | -27.0% ± 11.2% |
| USA · NBA — win:home | 49 | 44.9% | 54.0% | -9.1% | -27.4% ± 12.3% |
| Japan · B League One — win:away | 65 | 35.4% | 46.2% | -10.8% | -34.2% ± 12.9% |
| International · Euroleague — hcp:home | 32 | 34.4% | 50.2% | -15.8% | -34.7% ± 16.2% |
| Italy · Serie A2 — hcp:away | 34 | 35.3% | 49.9% | -14.6% | -35.6% ± 15.2% |
| International · Euroleague — win:home | 32 | 43.8% | 60.6% | -16.8% | -38.3% ± 12.9% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 176 | +0.0% | -5.2% |
| not covered | hcp | 2594 | +0.0% | -7.2% |
| covered | total | 176 | +0.0% | -5.2% |
| not covered | total | 2594 | +0.0% | -7.3% |
| covered | win | 176 | +0.0% | -7.1% |
| not covered | win | 2592 | +0.0% | -8.9% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 1242 | 49.9% | 50.2% | -0.3% | +2.4% ± 3.5% |
| steady | 5114 | 51.9% | 51.7% | +0.2% | -6.9% ± 1.3% |
| drifted 3%+ | 1370 | 43.1% | 43.5% | -0.4% | -18.2% ± 2.9% |

