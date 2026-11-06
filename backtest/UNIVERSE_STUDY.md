# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

11216 games graded (73% of 15467 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-11-06.

## Football — 9152 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 8999 | 31.7% | 32.3% | -0.6% | -13.2% ± 1.6% |
| 1x2:draw | 8999 | 23.2% | 24.7% | -1.4% | -14.9% ± 1.7% |
| 1x2:home | 8999 | 45.0% | 43.1% | +2.0% | -4.3% ± 1.4% |
| btts:no | 7689 | 44.7% | 45.9% | -1.1% | -10.4% ± 1.2% |
| btts:yes | 7689 | 55.3% | 54.1% | +1.1% | -6.2% ± 1.0% |
| dc:12 | 8579 | 76.8% | 74.5% | +2.3% | -4.7% ± 0.6% |
| dc:1x | 8579 | 68.1% | 67.5% | +0.6% | -8.5% ± 0.7% |
| dc:x2 | 8579 | 55.0% | 58.0% | -2.9% | -14.4% ± 0.9% |
| o/u1.5:over | 6888 | 76.8% | 74.6% | +2.2% | -3.9% ± 0.6% |
| o/u1.5:under | 6888 | 23.2% | 25.4% | -2.2% | -16.2% ± 1.9% |
| o/u2.5:over | 8485 | 55.7% | 54.0% | +1.7% | -4.1% ± 1.0% |
| o/u2.5:under | 8485 | 44.3% | 46.0% | -1.7% | -10.9% ± 1.1% |
| o/u3.5:over | 7759 | 36.5% | 36.1% | +0.4% | -6.9% ± 1.5% |
| o/u3.5:under | 7759 | 63.5% | 63.9% | -0.4% | -7.7% ± 0.8% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 711 | 83.4% | 78.4% | +5.0% | -1.7% ± 1.7% |
| 1x2 @ 1.30–1.60 | 1668 | 68.5% | 63.6% | +4.8% | -0.6% ± 1.7% |
| 1x2 @ 1.60–2.00 | 2706 | 54.2% | 51.6% | +2.6% | -3.1% ± 1.7% |
| 1x2 @ 2.00–3.00 | 6568 | 39.0% | 37.8% | +1.2% | -5.2% ± 1.5% |
| 1x2 @ 3.00–5.00 | 11976 | 23.8% | 25.4% | -1.6% | -14.1% ± 1.4% |
| 1x2 @ 5.00–1000.00 | 3368 | 11.3% | 13.6% | -2.3% | -23.0% ± 4.1% |
| btts @ 1.00–1.30 | 118 | 71.2% | 73.3% | -2.1% | -11.5% ± 5.2% |
| btts @ 1.30–1.60 | 3202 | 61.1% | 61.5% | -0.4% | -9.1% ± 1.3% |
| btts @ 1.60–2.00 | 7074 | 51.2% | 51.4% | -0.2% | -8.8% ± 1.1% |
| btts @ 2.00–3.00 | 4797 | 41.0% | 40.6% | +0.4% | -7.3% ± 1.6% |
| btts @ 3.00–5.00 | 187 | 31.0% | 28.0% | +3.1% | +2.7% ± 11.3% |
| dc @ 1.00–1.30 | 11799 | 80.7% | 77.4% | +3.3% | -3.6% ± 0.4% |
| dc @ 1.30–1.60 | 8089 | 66.2% | 66.2% | -0.0% | -7.5% ± 0.7% |
| dc @ 1.60–2.00 | 3233 | 46.9% | 52.9% | -6.0% | -18.0% ± 1.5% |
| dc @ 2.00–3.00 | 2012 | 33.4% | 40.2% | -6.7% | -23.3% ± 2.4% |
| dc @ 3.00–5.00 | 549 | 15.7% | 26.3% | -10.6% | -44.5% ± 5.6% |
| dc @ 5.00–1000.00 | 55 | 5.5% | 16.7% | -11.2% | -71.3% ± 16.3% |
| o/u1.5 @ 1.00–1.30 | 4640 | 81.1% | 78.5% | +2.6% | -3.3% ± 0.7% |
| o/u1.5 @ 1.30–1.60 | 2113 | 68.7% | 67.3% | +1.5% | -5.0% ± 1.4% |
| o/u1.5 @ 1.60–2.00 | 163 | 57.7% | 54.2% | +3.4% | -1.4% ± 6.7% |
| o/u1.5 @ 2.00–3.00 | 1318 | 35.0% | 35.9% | -0.9% | -9.9% ± 3.4% |
| o/u1.5 @ 3.00–5.00 | 4309 | 22.5% | 24.8% | -2.3% | -15.3% ± 2.4% |
| o/u1.5 @ 5.00–1000.00 | 1233 | 12.2% | 15.8% | -3.6% | -27.1% ± 5.7% |
| o/u2.5 @ 1.00–1.30 | 320 | 79.7% | 75.5% | +4.2% | -1.4% ± 2.8% |
| o/u2.5 @ 1.30–1.60 | 3437 | 64.8% | 63.2% | +1.6% | -4.5% ± 1.2% |
| o/u2.5 @ 1.60–2.00 | 6772 | 53.0% | 52.3% | +0.7% | -5.8% ± 1.1% |
| o/u2.5 @ 2.00–3.00 | 5740 | 39.1% | 40.7% | -1.6% | -10.5% ± 1.5% |
| o/u2.5 @ 3.00–5.00 | 672 | 24.4% | 27.9% | -3.5% | -17.7% ± 5.6% |
| o/u3.5 @ 1.00–1.30 | 1775 | 76.8% | 75.7% | +1.1% | -5.9% ± 1.2% |
| o/u3.5 @ 1.30–1.60 | 4053 | 64.9% | 65.1% | -0.2% | -6.9% ± 1.1% |
| o/u3.5 @ 1.60–2.00 | 2548 | 53.8% | 53.1% | +0.7% | -5.5% ± 1.7% |
| o/u3.5 @ 2.00–3.00 | 4421 | 38.7% | 38.7% | +0.0% | -6.3% ± 1.8% |
| o/u3.5 @ 3.00–5.00 | 2597 | 25.7% | 26.6% | -0.9% | -10.5% ± 3.0% |
| o/u3.5 @ 5.00–1000.00 | 124 | 10.5% | 16.8% | -6.3% | -43.4% ± 14.9% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Simulated Reality League · UEFA Champions League SRL — o/u3.5:over | 31 | 64.5% | 42.4% | +22.1% | +52.8% ± 21.8% |
| England Amateur · Southern League Premier Central — o/u3.5:over | 60 | 53.3% | 36.4% | +16.9% | +34.8% ± 16.6% |
| Japan · J1 League — o/u2.5:over | 44 | 70.5% | 51.6% | +18.8% | +34.6% ± 13.8% |
| Simulated Reality League · Serie A SRL — o/u2.5:over | 39 | 71.8% | 53.6% | +18.2% | +27.2% ± 13.3% |
| Turkiye Amateur · 2. Lig — o/u2.5:over | 30 | 76.7% | 55.6% | +21.1% | +26.7% ± 13.2% |
| Simulated Reality League · UEFA Champions League SRL — o/u2.5:over | 31 | 80.6% | 62.4% | +18.3% | +23.8% ± 11.5% |
| Spain · Primera Federacion — dc:1x | 59 | 86.4% | 69.3% | +17.2% | +15.4% ± 6.3% |
| Simulated Reality League · Serie A SRL — o/u1.5:over | 39 | 92.3% | 75.6% | +16.7% | +15.3% ± 5.5% |
| Spain · LaLiga 2 — o/u1.5:over | 35 | 88.6% | 72.2% | +16.3% | +15.3% ± 7.2% |
| Japan · J1 League — o/u1.5:over | 44 | 88.6% | 74.8% | +13.8% | +14.2% ± 6.4% |
| Turkiye · Super Lig — dc:12 | 32 | 90.6% | 75.4% | +15.3% | +14.1% ± 6.7% |
| Simulated Reality League · UEFA Champions League SRL — dc:12 | 31 | 93.5% | 77.1% | +16.4% | +14.0% ± 5.6% |
| Simulated Reality League · UEFA Europa League SRL — o/u1.5:over | 34 | 94.1% | 78.5% | +15.7% | +13.1% ± 5.1% |
| Germany · 3. Liga — o/u1.5:over | 31 | 96.8% | 81.9% | +14.9% | +11.5% ± 3.8% |
| Italy · Serie A — o/u1.5:over | 49 | 89.8% | 78.1% | +11.7% | +11.3% ± 5.6% |
| International Clubs · UEFA Champions League — dc:12 | 54 | 90.7% | 78.6% | +12.2% | +9.8% ± 4.9% |
| USA · MLS — dc:12 | 78 | 67.9% | 76.1% | -8.1% | -15.7% ± 6.6% |
| Sweden · Division 2 — dc:1x | 77 | 61.0% | 66.7% | -5.7% | -16.3% ± 8.0% |
| England · Championship — dc:1x | 66 | 60.6% | 68.4% | -7.8% | -17.8% ± 8.5% |
| Spain · Segunda Federacion — 1x2:home | 123 | 41.5% | 43.9% | -2.4% | -18.3% ± 9.1% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 3306 | +0.0% | -6.9% |
| not covered | 1x2 | 23691 | +0.0% | -11.3% |
| covered | btts | 2200 | +0.0% | -5.2% |
| not covered | btts | 13178 | +0.0% | -8.8% |
| covered | dc | 3306 | -0.0% | -7.4% |
| not covered | dc | 22431 | +0.0% | -9.5% |
| covered | o/u1.5 | 2186 | +0.0% | -8.5% |
| not covered | o/u1.5 | 11590 | +0.0% | -10.3% |
| covered | o/u2.5 | 2204 | +0.0% | -5.0% |
| not covered | o/u2.5 | 14766 | +0.0% | -7.9% |
| covered | o/u3.5 | 2204 | +0.0% | -5.8% |
| not covered | o/u3.5 | 13314 | +0.0% | -7.5% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 18212 | 48.3% | 48.3% | +0.1% | +0.1% ± 0.9% |
| steady | 56921 | 54.5% | 54.0% | +0.5% | -8.1% ± 0.4% |
| drifted 3%+ | 23954 | 38.9% | 40.1% | -1.2% | -19.7% ± 0.8% |

## Basketball — 2064 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 2056 | 51.2% | 50.1% | +1.1% | -5.1% ± 2.0% |
| hcp:home | 2056 | 48.8% | 49.9% | -1.1% | -9.1% ± 2.1% |
| total:over | 2054 | 50.4% | 50.1% | +0.3% | -6.5% ± 2.0% |
| total:under | 2054 | 49.6% | 49.9% | -0.3% | -7.7% ± 2.1% |
| win:away | 2054 | 41.9% | 41.7% | +0.2% | -11.4% ± 2.9% |
| win:home | 2054 | 58.1% | 58.3% | -0.2% | -8.9% ± 2.1% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 4093 | 50.1% | 50.0% | +0.1% | -7.0% ± 1.5% |
| total @ 1.60–2.00 | 4107 | 50.0% | 50.0% | +0.0% | -7.1% ± 1.5% |
| win @ 1.00–1.30 | 894 | 84.3% | 83.3% | +1.0% | -5.9% ± 1.4% |
| win @ 1.30–1.60 | 657 | 65.1% | 65.9% | -0.8% | -7.7% ± 2.6% |
| win @ 1.60–2.00 | 657 | 50.2% | 53.1% | -2.9% | -10.9% ± 3.5% |
| win @ 2.00–3.00 | 800 | 43.4% | 39.6% | +3.7% | +2.5% ± 4.2% |
| win @ 3.00–5.00 | 570 | 27.2% | 25.7% | +1.5% | -0.2% ± 6.9% |
| win @ 5.00–1000.00 | 530 | 7.5% | 12.0% | -4.5% | -49.3% ± 8.0% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| USA · NBA — win:home | 94 | 50.0% | 55.6% | -5.6% | -20.0% ± 8.9% |
| Japan · B League One — win:away | 93 | 41.9% | 48.4% | -6.5% | -23.7% ± 11.4% |
| Japan · B League One — total:over | 93 | 38.7% | 50.1% | -11.4% | -29.4% ± 9.3% |
| Italy · Serie A2 — hcp:away | 44 | 38.6% | 50.0% | -11.4% | -29.8% ± 13.5% |
| International · Euroleague — win:home | 45 | 44.4% | 60.3% | -15.9% | -32.6% ± 12.1% |
| International · FIBA Europe Cup — win:away | 62 | 33.9% | 41.3% | -7.4% | -34.7% ± 14.1% |
| China · CBA — win:away | 49 | 36.7% | 39.6% | -2.9% | -35.3% ± 13.6% |
| USA · NCAA, Regular Season — win:away | 143 | 18.2% | 18.7% | -0.6% | -36.2% ± 14.3% |
| International · FIBA Champions League — total:over | 31 | 32.3% | 50.0% | -17.8% | -39.6% ± 16.0% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 266 | +0.0% | -4.6% |
| not covered | hcp | 3846 | +0.0% | -7.3% |
| covered | total | 266 | +0.0% | -4.7% |
| not covered | total | 3842 | +0.0% | -7.3% |
| covered | win | 266 | +0.0% | -7.8% |
| not covered | win | 3842 | +0.0% | -10.3% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 1832 | 50.1% | 50.0% | +0.1% | +2.8% ± 2.9% |
| steady | 7602 | 52.0% | 51.9% | +0.1% | -7.4% ± 1.1% |
| drifted 3%+ | 2036 | 42.5% | 43.0% | -0.5% | -19.4% ± 2.4% |

