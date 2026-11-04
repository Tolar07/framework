# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

10871 games graded (72% of 15122 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-11-04.

## Football — 8953 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 8802 | 31.5% | 32.3% | -0.7% | -13.8% ± 1.6% |
| 1x2:draw | 8802 | 23.4% | 24.7% | -1.3% | -14.4% ± 1.7% |
| 1x2:home | 8802 | 45.1% | 43.0% | +2.0% | -4.1% ± 1.4% |
| btts:no | 7509 | 44.7% | 45.9% | -1.1% | -10.3% ± 1.2% |
| btts:yes | 7509 | 55.3% | 54.1% | +1.1% | -6.2% ± 1.0% |
| dc:12 | 8383 | 76.7% | 74.5% | +2.2% | -4.9% ± 0.6% |
| dc:1x | 8383 | 68.3% | 67.5% | +0.8% | -8.2% ± 0.7% |
| dc:x2 | 8383 | 55.0% | 58.0% | -3.0% | -14.5% ± 0.9% |
| o/u1.5:over | 6720 | 76.9% | 74.6% | +2.3% | -3.8% ± 0.7% |
| o/u1.5:under | 6720 | 23.1% | 25.4% | -2.3% | -16.3% ± 2.0% |
| o/u2.5:over | 8298 | 55.7% | 53.9% | +1.8% | -4.0% ± 1.0% |
| o/u2.5:under | 8298 | 44.3% | 46.1% | -1.8% | -11.0% ± 1.2% |
| o/u3.5:over | 7586 | 36.5% | 36.1% | +0.4% | -6.9% ± 1.5% |
| o/u3.5:under | 7586 | 63.5% | 63.9% | -0.4% | -7.6% ± 0.8% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 690 | 83.2% | 78.4% | +4.8% | -2.0% ± 1.7% |
| 1x2 @ 1.30–1.60 | 1625 | 68.3% | 63.6% | +4.7% | -0.8% ± 1.7% |
| 1x2 @ 1.60–2.00 | 2648 | 54.2% | 51.6% | +2.6% | -3.1% ± 1.7% |
| 1x2 @ 2.00–3.00 | 6447 | 39.0% | 37.8% | +1.2% | -5.4% ± 1.5% |
| 1x2 @ 3.00–5.00 | 11732 | 23.9% | 25.4% | -1.5% | -13.9% ± 1.4% |
| 1x2 @ 5.00–1000.00 | 3264 | 11.2% | 13.6% | -2.3% | -23.4% ± 4.1% |
| btts @ 1.00–1.30 | 118 | 71.2% | 73.3% | -2.1% | -11.5% ± 5.2% |
| btts @ 1.30–1.60 | 3129 | 61.0% | 61.5% | -0.5% | -9.4% ± 1.3% |
| btts @ 1.60–2.00 | 6905 | 51.2% | 51.4% | -0.2% | -8.9% ± 1.1% |
| btts @ 2.00–3.00 | 4683 | 41.1% | 40.6% | +0.5% | -7.0% ± 1.6% |
| btts @ 3.00–5.00 | 183 | 31.7% | 27.9% | +3.8% | +5.0% ± 11.5% |
| dc @ 1.00–1.30 | 11522 | 80.6% | 77.4% | +3.3% | -3.7% ± 0.4% |
| dc @ 1.30–1.60 | 7922 | 66.2% | 66.2% | +0.0% | -7.5% ± 0.7% |
| dc @ 1.60–2.00 | 3163 | 46.9% | 52.9% | -5.9% | -17.9% ± 1.6% |
| dc @ 2.00–3.00 | 1961 | 33.6% | 40.2% | -6.6% | -23.1% ± 2.5% |
| dc @ 3.00–5.00 | 529 | 15.9% | 26.3% | -10.4% | -43.6% ± 5.7% |
| dc @ 5.00–1000.00 | 52 | 3.8% | 16.6% | -12.8% | -79.8% ± 14.2% |
| o/u1.5 @ 1.00–1.30 | 4520 | 81.0% | 78.4% | +2.6% | -3.3% ± 0.7% |
| o/u1.5 @ 1.30–1.60 | 2069 | 69.0% | 67.3% | +1.7% | -4.7% ± 1.4% |
| o/u1.5 @ 1.60–2.00 | 159 | 58.5% | 54.2% | +4.3% | +0.1% ± 6.7% |
| o/u1.5 @ 2.00–3.00 | 1288 | 34.5% | 35.8% | -1.4% | -11.0% ± 3.4% |
| o/u1.5 @ 3.00–5.00 | 4212 | 22.5% | 24.8% | -2.4% | -15.4% ± 2.5% |
| o/u1.5 @ 5.00–1000.00 | 1192 | 12.4% | 15.9% | -3.4% | -26.1% ± 5.8% |
| o/u2.5 @ 1.00–1.30 | 313 | 79.6% | 75.5% | +4.1% | -1.5% ± 2.8% |
| o/u2.5 @ 1.30–1.60 | 3343 | 64.6% | 63.2% | +1.5% | -4.7% ± 1.2% |
| o/u2.5 @ 1.60–2.00 | 6641 | 53.0% | 52.3% | +0.8% | -5.7% ± 1.1% |
| o/u2.5 @ 2.00–3.00 | 5622 | 39.1% | 40.8% | -1.6% | -10.5% ± 1.5% |
| o/u2.5 @ 3.00–5.00 | 648 | 24.7% | 27.9% | -3.2% | -16.8% ± 5.8% |
| o/u3.5 @ 1.00–1.30 | 1747 | 76.8% | 75.7% | +1.0% | -6.0% ± 1.2% |
| o/u3.5 @ 1.30–1.60 | 3961 | 64.9% | 65.1% | -0.2% | -7.0% ± 1.1% |
| o/u3.5 @ 1.60–2.00 | 2487 | 53.8% | 53.1% | +0.8% | -5.3% ± 1.8% |
| o/u3.5 @ 2.00–3.00 | 4305 | 38.8% | 38.7% | +0.1% | -6.2% ± 1.8% |
| o/u3.5 @ 3.00–5.00 | 2550 | 25.7% | 26.6% | -0.9% | -10.5% ± 3.0% |
| o/u3.5 @ 5.00–1000.00 | 122 | 10.7% | 16.8% | -6.1% | -42.5% ± 15.2% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| England Amateur · Southern League Premier Central — o/u3.5:over | 60 | 53.3% | 36.4% | +16.9% | +34.8% ± 16.6% |
| Japan · J1 League — o/u2.5:over | 44 | 70.5% | 51.6% | +18.8% | +34.6% ± 13.8% |
| Simulated Reality League · Serie A SRL — o/u2.5:over | 39 | 71.8% | 53.6% | +18.2% | +27.2% ± 13.3% |
| Turkiye Amateur · 2. Lig — o/u2.5:over | 30 | 76.7% | 55.6% | +21.1% | +26.7% ± 13.2% |
| Brazil · Brasileiro Serie A — dc:1x | 31 | 90.3% | 72.2% | +18.2% | +18.2% ± 8.0% |
| Spain · Primera Federacion — dc:1x | 59 | 86.4% | 69.3% | +17.2% | +15.4% ± 6.3% |
| Simulated Reality League · Serie A SRL — o/u1.5:over | 39 | 92.3% | 75.6% | +16.7% | +15.3% ± 5.5% |
| Spain · LaLiga 2 — o/u1.5:over | 35 | 88.6% | 72.2% | +16.3% | +15.3% ± 7.2% |
| Japan · J1 League — o/u1.5:over | 44 | 88.6% | 74.8% | +13.8% | +14.2% ± 6.4% |
| Turkiye · Super Lig — dc:12 | 32 | 90.6% | 75.4% | +15.3% | +14.1% ± 6.7% |
| Germany · 3. Liga — o/u1.5:over | 31 | 96.8% | 81.9% | +14.9% | +11.5% ± 3.8% |
| Italy · Serie A — o/u1.5:over | 49 | 89.8% | 78.1% | +11.7% | +11.3% ± 5.6% |
| USA · MLS — dc:12 | 78 | 67.9% | 76.1% | -8.1% | -15.7% ± 6.6% |
| Sweden · Division 2 — dc:1x | 77 | 61.0% | 66.7% | -5.7% | -16.3% ± 8.0% |
| Spain · Segunda Federacion — 1x2:home | 123 | 41.5% | 43.9% | -2.4% | -18.3% ± 9.1% |
| England · Championship — dc:1x | 63 | 60.3% | 69.2% | -8.9% | -20.1% ± 8.4% |
| Spain · Segunda Federacion — dc:12 | 123 | 62.6% | 71.7% | -9.1% | -20.7% ± 5.6% |
| China · China League 2 — dc:12 | 39 | 61.5% | 70.6% | -9.0% | -20.8% ± 10.2% |
| England Amateur · National League South — dc:1x | 53 | 60.4% | 66.7% | -6.3% | -21.2% ± 9.1% |
| Sweden · Allsvenskan — o/u1.5:over | 38 | 65.8% | 78.9% | -13.1% | -21.5% ± 9.3% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 3177 | +0.0% | -7.6% |
| not covered | 1x2 | 23229 | +0.0% | -11.2% |
| covered | btts | 2114 | +0.0% | -5.1% |
| not covered | btts | 12904 | +0.0% | -8.8% |
| covered | dc | 3177 | -0.0% | -7.6% |
| not covered | dc | 21972 | +0.0% | -9.4% |
| covered | o/u1.5 | 2100 | +0.0% | -8.6% |
| not covered | o/u1.5 | 11340 | +0.0% | -10.3% |
| covered | o/u2.5 | 2118 | +0.0% | -5.2% |
| not covered | o/u2.5 | 14478 | +0.0% | -7.8% |
| covered | o/u3.5 | 2118 | +0.0% | -5.7% |
| not covered | o/u3.5 | 13054 | +0.0% | -7.5% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 17748 | 48.3% | 48.2% | +0.1% | +0.3% ± 1.0% |
| steady | 55676 | 54.4% | 54.0% | +0.5% | -8.1% ± 0.4% |
| drifted 3%+ | 23343 | 39.0% | 40.2% | -1.2% | -19.7% ± 0.8% |

## Basketball — 1918 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 1910 | 51.0% | 50.1% | +0.9% | -5.4% ± 2.1% |
| hcp:home | 1910 | 49.0% | 49.9% | -0.9% | -8.8% ± 2.1% |
| total:over | 1909 | 50.7% | 50.1% | +0.6% | -6.0% ± 2.1% |
| total:under | 1909 | 49.3% | 49.9% | -0.6% | -8.3% ± 2.1% |
| win:away | 1908 | 42.0% | 42.2% | -0.1% | -11.3% ± 3.0% |
| win:home | 1908 | 58.0% | 57.8% | +0.1% | -8.0% ± 2.2% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 3803 | 50.1% | 50.0% | +0.1% | -7.0% ± 1.5% |
| total @ 1.60–2.00 | 3817 | 50.0% | 50.0% | +0.0% | -7.1% ± 1.5% |
| win @ 1.00–1.30 | 815 | 83.8% | 83.1% | +0.7% | -6.3% ± 1.5% |
| win @ 1.30–1.60 | 620 | 65.0% | 65.9% | -0.9% | -8.0% ± 2.7% |
| win @ 1.60–2.00 | 620 | 50.0% | 53.1% | -3.1% | -11.2% ± 3.6% |
| win @ 2.00–3.00 | 752 | 43.8% | 39.6% | +4.1% | +3.3% ± 4.3% |
| win @ 3.00–5.00 | 536 | 27.2% | 25.7% | +1.5% | +0.1% ± 7.2% |
| win @ 5.00–1000.00 | 473 | 7.8% | 12.1% | -4.3% | -47.3% ± 8.6% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| USA · NBA — win:home | 79 | 48.1% | 55.1% | -7.0% | -22.7% ± 9.7% |
| Japan · B League One — total:over | 84 | 40.5% | 50.1% | -9.6% | -26.2% ± 9.8% |
| Italy · Serie A2 — hcp:away | 42 | 38.1% | 50.0% | -11.9% | -30.7% ± 13.8% |
| China · CBA — win:away | 49 | 36.7% | 39.6% | -2.9% | -35.3% ± 13.6% |
| USA · NCAA, Regular Season — win:away | 103 | 15.5% | 17.7% | -2.1% | -39.2% ± 17.9% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 236 | +0.0% | -4.7% |
| not covered | hcp | 3584 | +0.0% | -7.3% |
| covered | total | 236 | +0.0% | -4.9% |
| not covered | total | 3582 | +0.0% | -7.3% |
| covered | win | 236 | +0.0% | -7.5% |
| not covered | win | 3580 | +0.0% | -9.8% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 1689 | 50.3% | 50.1% | +0.2% | +3.2% ± 3.0% |
| steady | 7145 | 51.9% | 51.8% | +0.1% | -7.1% ± 1.1% |
| drifted 3%+ | 1880 | 42.4% | 43.1% | -0.7% | -19.6% ± 2.5% |

