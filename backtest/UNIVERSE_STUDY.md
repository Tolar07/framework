# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

10663 games graded (71% of 14914 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-11-03.

## Football — 8806 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 8658 | 31.5% | 32.3% | -0.8% | -13.8% ± 1.6% |
| 1x2:draw | 8658 | 23.5% | 24.7% | -1.2% | -14.1% ± 1.7% |
| 1x2:home | 8658 | 45.0% | 43.1% | +2.0% | -4.2% ± 1.4% |
| btts:no | 7382 | 44.5% | 45.9% | -1.4% | -11.0% ± 1.2% |
| btts:yes | 7382 | 55.5% | 54.1% | +1.4% | -5.8% ± 1.0% |
| dc:12 | 8239 | 76.6% | 74.5% | +2.1% | -5.0% ± 0.6% |
| dc:1x | 8239 | 68.4% | 67.6% | +0.8% | -8.2% ± 0.7% |
| dc:x2 | 8239 | 55.0% | 58.0% | -2.9% | -14.3% ± 0.9% |
| o/u1.5:over | 6609 | 77.0% | 74.5% | +2.4% | -3.6% ± 0.7% |
| o/u1.5:under | 6609 | 23.0% | 25.5% | -2.4% | -16.8% ± 2.0% |
| o/u2.5:over | 8164 | 55.9% | 53.9% | +2.0% | -3.7% ± 1.0% |
| o/u2.5:under | 8164 | 44.1% | 46.1% | -2.0% | -11.4% ± 1.2% |
| o/u3.5:over | 7451 | 36.6% | 36.0% | +0.6% | -6.5% ± 1.5% |
| o/u3.5:under | 7451 | 63.4% | 64.0% | -0.6% | -8.0% ± 0.8% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 675 | 83.3% | 78.4% | +4.9% | -1.9% ± 1.7% |
| 1x2 @ 1.30–1.60 | 1601 | 68.0% | 63.6% | +4.4% | -1.3% ± 1.7% |
| 1x2 @ 1.60–2.00 | 2606 | 54.2% | 51.6% | +2.6% | -3.2% ± 1.8% |
| 1x2 @ 2.00–3.00 | 6343 | 38.9% | 37.8% | +1.1% | -5.5% ± 1.5% |
| 1x2 @ 3.00–5.00 | 11540 | 23.9% | 25.4% | -1.5% | -13.6% ± 1.4% |
| 1x2 @ 5.00–1000.00 | 3209 | 11.3% | 13.6% | -2.3% | -23.1% ± 4.1% |
| btts @ 1.00–1.30 | 118 | 71.2% | 73.3% | -2.1% | -11.5% ± 5.2% |
| btts @ 1.30–1.60 | 3059 | 61.4% | 61.5% | -0.2% | -8.8% ± 1.3% |
| btts @ 1.60–2.00 | 6805 | 51.2% | 51.4% | -0.1% | -8.8% ± 1.1% |
| btts @ 2.00–3.00 | 4600 | 40.8% | 40.6% | +0.2% | -7.8% ± 1.6% |
| btts @ 3.00–5.00 | 182 | 31.3% | 27.9% | +3.4% | +3.6% ± 11.5% |
| dc @ 1.00–1.30 | 11329 | 80.5% | 77.3% | +3.2% | -3.8% ± 0.4% |
| dc @ 1.30–1.60 | 7785 | 66.2% | 66.2% | +0.0% | -7.6% ± 0.8% |
| dc @ 1.60–2.00 | 3107 | 47.1% | 52.9% | -5.8% | -17.7% ± 1.6% |
| dc @ 2.00–3.00 | 1929 | 33.9% | 40.2% | -6.3% | -22.3% ± 2.5% |
| dc @ 3.00–5.00 | 517 | 15.7% | 26.3% | -10.6% | -44.5% ± 5.7% |
| dc @ 5.00–1000.00 | 50 | 4.0% | 16.5% | -12.5% | -79.0% ± 14.7% |
| o/u1.5 @ 1.00–1.30 | 4445 | 81.1% | 78.4% | +2.7% | -3.2% ± 0.7% |
| o/u1.5 @ 1.30–1.60 | 2035 | 69.2% | 67.3% | +2.0% | -4.3% ± 1.4% |
| o/u1.5 @ 1.60–2.00 | 155 | 58.7% | 54.3% | +4.4% | +0.4% ± 6.8% |
| o/u1.5 @ 2.00–3.00 | 1275 | 34.3% | 35.8% | -1.6% | -11.6% ± 3.5% |
| o/u1.5 @ 3.00–5.00 | 4143 | 22.3% | 24.8% | -2.6% | -16.2% ± 2.5% |
| o/u1.5 @ 5.00–1000.00 | 1165 | 12.5% | 15.9% | -3.3% | -25.7% ± 5.9% |
| o/u2.5 @ 1.00–1.30 | 304 | 80.3% | 75.5% | +4.8% | -0.7% ± 2.8% |
| o/u2.5 @ 1.30–1.60 | 3283 | 64.6% | 63.2% | +1.4% | -4.8% ± 1.2% |
| o/u2.5 @ 1.60–2.00 | 6557 | 53.0% | 52.3% | +0.8% | -5.7% ± 1.1% |
| o/u2.5 @ 2.00–3.00 | 5524 | 39.2% | 40.8% | -1.6% | -10.4% ± 1.5% |
| o/u2.5 @ 3.00–5.00 | 632 | 24.2% | 27.9% | -3.7% | -18.6% ± 5.8% |
| o/u3.5 @ 1.00–1.30 | 1722 | 76.5% | 75.7% | +0.8% | -6.3% ± 1.3% |
| o/u3.5 @ 1.30–1.60 | 3897 | 64.8% | 65.1% | -0.3% | -7.1% ± 1.1% |
| o/u3.5 @ 1.60–2.00 | 2432 | 53.8% | 53.1% | +0.8% | -5.4% ± 1.8% |
| o/u3.5 @ 2.00–3.00 | 4218 | 38.8% | 38.7% | +0.1% | -6.1% ± 1.8% |
| o/u3.5 @ 3.00–5.00 | 2511 | 25.8% | 26.6% | -0.7% | -10.0% ± 3.1% |
| o/u3.5 @ 5.00–1000.00 | 122 | 10.7% | 16.8% | -6.1% | -42.5% ± 15.2% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| England Amateur · Southern League Premier Central — o/u3.5:over | 58 | 53.4% | 36.3% | +17.1% | +35.0% ± 16.9% |
| Japan · J1 League — o/u2.5:over | 44 | 70.5% | 51.6% | +18.8% | +34.6% ± 13.8% |
| Simulated Reality League · Serie A SRL — o/u2.5:over | 39 | 71.8% | 53.6% | +18.2% | +27.2% ± 13.3% |
| Turkiye Amateur · 2. Lig — o/u2.5:over | 30 | 76.7% | 55.6% | +21.1% | +26.7% ± 13.2% |
| Spain · Primera Federacion — dc:1x | 59 | 86.4% | 69.3% | +17.2% | +15.4% ± 6.3% |
| Simulated Reality League · Serie A SRL — o/u1.5:over | 39 | 92.3% | 75.6% | +16.7% | +15.3% ± 5.5% |
| Spain · LaLiga 2 — o/u1.5:over | 35 | 88.6% | 72.2% | +16.3% | +15.3% ± 7.2% |
| Japan · J3 League — dc:12 | 40 | 90.0% | 72.8% | +17.2% | +14.5% ± 6.1% |
| Japan · J1 League — o/u1.5:over | 44 | 88.6% | 74.8% | +13.8% | +14.2% ± 6.4% |
| Turkiye · Super Lig — dc:12 | 32 | 90.6% | 75.4% | +15.3% | +14.1% ± 6.7% |
| Germany · 3. Liga — o/u1.5:over | 31 | 96.8% | 81.9% | +14.9% | +11.5% ± 3.8% |
| Italy · Serie A — o/u1.5:over | 49 | 89.8% | 78.1% | +11.7% | +11.3% ± 5.6% |
| USA · MLS — dc:12 | 78 | 67.9% | 76.1% | -8.1% | -15.7% ± 6.6% |
| Sweden · Division 2 — dc:1x | 77 | 61.0% | 66.7% | -5.7% | -16.3% ± 8.0% |
| Spain · Segunda Federacion — 1x2:home | 123 | 41.5% | 43.9% | -2.4% | -18.3% ± 9.1% |
| England · Championship — dc:1x | 55 | 61.8% | 70.0% | -8.2% | -18.9% ± 8.9% |
| England Amateur · National League South — dc:1x | 51 | 60.8% | 66.8% | -6.0% | -20.4% ± 9.3% |
| Spain · Segunda Federacion — dc:12 | 123 | 62.6% | 71.7% | -9.1% | -20.7% ± 5.6% |
| China · China League 2 — dc:12 | 39 | 61.5% | 70.6% | -9.0% | -20.8% ± 10.2% |
| England Amateur · Southern League Premier South — o/u3.5:under | 49 | 53.1% | 62.2% | -9.1% | -21.9% ± 10.6% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 3108 | +0.0% | -7.4% |
| not covered | 1x2 | 22866 | +0.0% | -11.1% |
| covered | btts | 2068 | +0.0% | -5.4% |
| not covered | btts | 12696 | +0.0% | -8.8% |
| covered | dc | 3108 | +0.0% | -7.5% |
| not covered | dc | 21609 | +0.0% | -9.4% |
| covered | o/u1.5 | 2054 | +0.0% | -9.2% |
| not covered | o/u1.5 | 11164 | +0.0% | -10.4% |
| covered | o/u2.5 | 2072 | +0.0% | -5.4% |
| not covered | o/u2.5 | 14256 | +0.0% | -7.8% |
| covered | o/u3.5 | 2072 | +0.0% | -5.7% |
| not covered | o/u3.5 | 12830 | +0.0% | -7.4% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 17420 | 48.4% | 48.2% | +0.2% | +0.2% ± 1.0% |
| steady | 54801 | 54.4% | 54.0% | +0.5% | -8.0% ± 0.4% |
| drifted 3%+ | 22922 | 39.0% | 40.2% | -1.3% | -19.8% ± 0.8% |

## Basketball — 1857 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 1849 | 50.8% | 50.1% | +0.7% | -5.8% ± 2.2% |
| hcp:home | 1849 | 49.2% | 49.9% | -0.7% | -8.4% ± 2.2% |
| total:over | 1848 | 50.9% | 50.1% | +0.8% | -5.7% ± 2.2% |
| total:under | 1848 | 49.1% | 49.9% | -0.8% | -8.6% ± 2.2% |
| win:away | 1847 | 42.5% | 42.5% | +0.0% | -10.4% ± 3.1% |
| win:home | 1847 | 57.5% | 57.5% | -0.0% | -8.5% ± 2.3% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 3683 | 50.1% | 50.0% | +0.1% | -7.0% ± 1.5% |
| total @ 1.60–2.00 | 3695 | 50.0% | 50.0% | +0.0% | -7.1% ± 1.5% |
| win @ 1.00–1.30 | 777 | 83.7% | 82.9% | +0.7% | -6.2% ± 1.5% |
| win @ 1.30–1.60 | 605 | 64.8% | 65.9% | -1.1% | -8.2% ± 2.8% |
| win @ 1.60–2.00 | 609 | 49.9% | 53.1% | -3.2% | -11.4% ± 3.6% |
| win @ 2.00–3.00 | 738 | 44.0% | 39.6% | +4.4% | +4.0% ± 4.4% |
| win @ 3.00–5.00 | 521 | 27.3% | 25.7% | +1.5% | -0.0% ± 7.3% |
| win @ 5.00–1000.00 | 444 | 7.7% | 12.2% | -4.5% | -47.5% ± 9.0% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| USA · NBA — win:home | 79 | 48.1% | 55.1% | -7.0% | -22.7% ± 9.7% |
| Japan · B League One — total:over | 84 | 40.5% | 50.1% | -9.6% | -26.2% ± 9.8% |
| Italy · Serie A2 — hcp:away | 42 | 38.1% | 50.0% | -11.9% | -30.7% ± 13.8% |
| China · CBA — win:away | 45 | 37.8% | 40.8% | -3.0% | -32.4% ± 14.6% |
| International · FIBA Europe Cup — win:away | 47 | 34.0% | 43.7% | -9.6% | -33.4% ± 16.2% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 236 | +0.0% | -4.7% |
| not covered | hcp | 3462 | +0.0% | -7.3% |
| covered | total | 236 | +0.0% | -4.9% |
| not covered | total | 3460 | +0.0% | -7.3% |
| covered | win | 236 | +0.0% | -7.5% |
| not covered | win | 3458 | +0.0% | -9.6% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 1626 | 50.4% | 50.2% | +0.2% | +3.5% ± 3.0% |
| steady | 6914 | 51.9% | 51.7% | +0.1% | -7.0% ± 1.1% |
| drifted 3%+ | 1816 | 42.4% | 43.2% | -0.8% | -19.6% ± 2.5% |

