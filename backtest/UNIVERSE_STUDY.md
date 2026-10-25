# UNIVERSE STUDY — SportyBet's prices on every game, covered or not

Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` (`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price with SportyBet's margin removed. A study, not a selector.

6883 games graded (74% of 9291 looked up; the rest had no unambiguous result on Flashscore), kick-offs 2026-10-07 to 2026-10-25.

## Football — 5716 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2:away | 5640 | 31.5% | 32.2% | -0.7% | -13.9% ± 2.0% |
| 1x2:draw | 5640 | 23.5% | 24.6% | -1.1% | -13.5% ± 2.2% |
| 1x2:home | 5640 | 45.0% | 43.2% | +1.8% | -4.5% ± 1.8% |
| btts:no | 4841 | 44.0% | 45.7% | -1.7% | -11.6% ± 1.5% |
| btts:yes | 4841 | 56.0% | 54.3% | +1.7% | -5.2% ± 1.2% |
| dc:12 | 5408 | 76.4% | 74.5% | +1.9% | -5.2% ± 0.7% |
| dc:1x | 5408 | 68.4% | 67.7% | +0.8% | -8.0% ± 0.9% |
| dc:x2 | 5408 | 55.1% | 57.8% | -2.7% | -14.1% ± 1.1% |
| o/u1.5:over | 4276 | 76.8% | 74.5% | +2.3% | -3.7% ± 0.8% |
| o/u1.5:under | 4276 | 23.2% | 25.5% | -2.3% | -15.4% ± 2.5% |
| o/u2.5:over | 5303 | 56.7% | 54.1% | +2.6% | -2.5% ± 1.2% |
| o/u2.5:under | 5303 | 43.3% | 45.9% | -2.6% | -12.8% ± 1.4% |
| o/u3.5:over | 4886 | 37.4% | 36.2% | +1.2% | -4.8% ± 1.9% |
| o/u3.5:under | 4886 | 62.6% | 63.8% | -1.2% | -8.9% ± 1.0% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| 1x2 @ 1.00–1.30 | 448 | 82.6% | 78.2% | +4.4% | -2.4% ± 2.1% |
| 1x2 @ 1.30–1.60 | 1060 | 68.5% | 63.6% | +4.9% | -0.6% ± 2.1% |
| 1x2 @ 1.60–2.00 | 1698 | 54.2% | 51.5% | +2.6% | -3.1% ± 2.2% |
| 1x2 @ 2.00–3.00 | 4114 | 38.9% | 37.8% | +1.1% | -5.3% ± 1.9% |
| 1x2 @ 3.00–5.00 | 7485 | 23.8% | 25.4% | -1.6% | -14.1% ± 1.8% |
| 1x2 @ 5.00–1000.00 | 2115 | 11.5% | 13.6% | -2.1% | -21.6% ± 5.1% |
| btts @ 1.00–1.30 | 96 | 71.9% | 73.2% | -1.3% | -10.7% ± 5.7% |
| btts @ 1.30–1.60 | 2022 | 61.4% | 61.6% | -0.2% | -8.9% ± 1.6% |
| btts @ 1.60–2.00 | 4416 | 51.4% | 51.3% | +0.1% | -8.6% ± 1.3% |
| btts @ 2.00–3.00 | 3009 | 40.4% | 40.5% | -0.1% | -8.5% ± 2.0% |
| btts @ 3.00–5.00 | 139 | 31.7% | 27.8% | +3.8% | +4.8% ± 13.2% |
| dc @ 1.00–1.30 | 7447 | 80.4% | 77.4% | +3.1% | -3.9% ± 0.6% |
| dc @ 1.30–1.60 | 5104 | 66.1% | 66.2% | -0.1% | -7.7% ± 0.9% |
| dc @ 1.60–2.00 | 2027 | 47.6% | 52.9% | -5.3% | -16.9% ± 1.9% |
| dc @ 2.00–3.00 | 1274 | 33.9% | 40.1% | -6.2% | -22.0% ± 3.1% |
| dc @ 3.00–5.00 | 343 | 15.5% | 26.4% | -11.0% | -44.7% ± 7.1% |
| o/u1.5 @ 1.00–1.30 | 2856 | 80.9% | 78.4% | +2.4% | -3.4% ± 0.9% |
| o/u1.5 @ 1.30–1.60 | 1335 | 69.2% | 67.3% | +1.9% | -4.4% ± 1.8% |
| o/u1.5 @ 1.60–2.00 | 105 | 61.0% | 53.9% | +7.0% | +4.9% ± 8.3% |
| o/u1.5 @ 2.00–3.00 | 822 | 34.3% | 35.8% | -1.5% | -11.0% ± 4.3% |
| o/u1.5 @ 3.00–5.00 | 2689 | 22.0% | 24.8% | -2.8% | -16.9% ± 3.1% |
| o/u1.5 @ 5.00–1000.00 | 745 | 14.0% | 15.9% | -1.9% | -15.9% ± 7.8% |
| o/u2.5 @ 1.00–1.30 | 206 | 79.6% | 75.4% | +4.2% | -1.4% ± 3.5% |
| o/u2.5 @ 1.30–1.60 | 2172 | 64.6% | 63.2% | +1.4% | -5.0% ± 1.5% |
| o/u2.5 @ 1.60–2.00 | 4170 | 53.4% | 52.3% | +1.1% | -5.2% ± 1.4% |
| o/u2.5 @ 2.00–3.00 | 3605 | 38.9% | 40.7% | -1.8% | -11.0% ± 1.9% |
| o/u2.5 @ 3.00–5.00 | 434 | 24.0% | 27.9% | -4.0% | -19.0% ± 7.0% |
| o/u3.5 @ 1.00–1.30 | 1127 | 75.5% | 75.8% | -0.3% | -7.5% ± 1.6% |
| o/u3.5 @ 1.30–1.60 | 2539 | 64.6% | 65.1% | -0.5% | -7.5% ± 1.4% |
| o/u3.5 @ 1.60–2.00 | 1643 | 53.7% | 52.9% | +0.8% | -5.3% ± 2.2% |
| o/u3.5 @ 2.00–3.00 | 2748 | 39.0% | 38.7% | +0.4% | -5.5% ± 2.3% |
| o/u3.5 @ 3.00–5.00 | 1638 | 26.3% | 26.5% | -0.2% | -7.6% ± 3.9% |
| o/u3.5 @ 5.00–1000.00 | 77 | 10.4% | 16.5% | -6.1% | -42.7% ± 19.3% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Sweden · Division 2 — dc:12 | 74 | 90.5% | 76.2% | +14.4% | +9.0% ± 4.2% |
| Sweden · Division 2 — dc:1x | 74 | 60.8% | 66.7% | -5.9% | -16.8% ± 8.2% |
| England · Championship — dc:1x | 44 | 59.1% | 68.8% | -9.7% | -20.7% ± 10.3% |
| USA · MLS — dc:12 | 48 | 62.5% | 75.8% | -13.3% | -22.3% ± 8.8% |
| Spain · Segunda Federacion — 1x2:home | 84 | 39.3% | 44.0% | -4.7% | -22.5% ± 10.9% |
| Spain · Segunda Federacion — dc:12 | 84 | 59.5% | 71.5% | -12.0% | -24.3% ± 6.9% |
| Sweden · Division 2 — dc:x2 | 74 | 48.6% | 57.2% | -8.5% | -24.7% ± 9.4% |
| Romania · Liga 3 — dc:x2 | 42 | 45.2% | 54.9% | -9.7% | -28.5% ± 13.3% |
| Sweden · Ettan — o/u3.5:under | 30 | 46.7% | 60.5% | -13.9% | -29.5% ± 14.0% |
| England · League One — dc:x2 | 44 | 45.5% | 56.6% | -11.1% | -30.5% ± 12.1% |
| Turkiye · 1. Lig — dc:1x | 34 | 52.9% | 67.9% | -14.9% | -31.8% ± 11.3% |
| International Clubs · UEFA Champions League — o/u3.5:under | 36 | 36.1% | 52.3% | -16.2% | -34.2% ± 14.9% |
| Sweden · Division 2 — o/u3.5:under | 67 | 38.8% | 53.3% | -14.5% | -34.5% ± 10.2% |
| Hungary · NB III — 1x2:away | 52 | 28.8% | 31.7% | -2.9% | -35.4% ± 15.9% |
| Spain · Segunda Federacion — 1x2:away | 84 | 20.2% | 28.2% | -8.0% | -36.3% ± 14.4% |
| England · League One — o/u3.5:over | 44 | 25.0% | 36.3% | -11.3% | -38.0% ± 16.8% |
| Sweden · Division 2 — o/u2.5:under | 66 | 22.7% | 34.4% | -11.7% | -38.1% ± 14.3% |
| Turkiye · 1. Lig — 1x2:home | 34 | 32.4% | 42.0% | -9.7% | -38.4% ± 16.0% |
| England · League One — 1x2:away | 44 | 22.7% | 31.2% | -8.4% | -39.2% ± 18.3% |
| International Youth · UEFA Youth League — dc:x2 | 31 | 35.5% | 52.0% | -16.5% | -40.8% ± 16.0% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | 1x2 | 2046 | -0.0% | -6.2% |
| not covered | 1x2 | 14874 | -0.0% | -11.3% |
| covered | btts | 1362 | +0.0% | -5.0% |
| not covered | btts | 8320 | +0.0% | -9.0% |
| covered | dc | 2046 | +0.0% | -7.0% |
| not covered | dc | 14178 | -0.0% | -9.4% |
| covered | o/u1.5 | 1354 | +0.0% | -6.8% |
| not covered | o/u1.5 | 7198 | +0.0% | -10.1% |
| covered | o/u2.5 | 1364 | +0.0% | -5.4% |
| not covered | o/u2.5 | 9242 | +0.0% | -8.0% |
| covered | o/u3.5 | 1364 | +0.0% | -5.8% |
| not covered | o/u3.5 | 8408 | +0.0% | -7.0% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 11864 | 48.8% | 48.5% | +0.3% | +0.3% ± 1.1% |
| steady | 35198 | 54.7% | 54.3% | +0.4% | -8.1% ± 0.5% |
| drifted 3%+ | 15637 | 39.0% | 40.2% | -1.2% | -19.5% ± 0.9% |

## Basketball — 1167 games

### Every market side

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp:away | 1163 | 50.3% | 50.1% | +0.2% | -6.8% ± 2.7% |
| hcp:home | 1163 | 49.7% | 49.9% | -0.2% | -7.6% ± 2.7% |
| total:over | 1162 | 50.9% | 50.1% | +0.8% | -5.7% ± 2.7% |
| total:under | 1162 | 49.1% | 49.9% | -0.8% | -8.7% ± 2.7% |
| win:away | 1160 | 42.3% | 43.0% | -0.6% | -11.6% ± 3.8% |
| win:home | 1160 | 57.7% | 57.0% | +0.6% | -7.1% ± 2.9% |

### By price band (all sides of a market together)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| hcp @ 1.60–2.00 | 2318 | 50.0% | 50.0% | +0.0% | -7.1% ± 1.9% |
| total @ 1.60–2.00 | 2323 | 50.0% | 50.0% | +0.0% | -7.2% ± 1.9% |
| win @ 1.00–1.30 | 467 | 83.1% | 82.5% | +0.6% | -6.4% ± 2.0% |
| win @ 1.30–1.60 | 396 | 65.9% | 65.9% | -0.0% | -6.9% ± 3.4% |
| win @ 1.60–2.00 | 382 | 50.3% | 53.1% | -2.9% | -10.9% ± 4.6% |
| win @ 2.00–3.00 | 492 | 42.9% | 39.6% | +3.3% | +1.1% ± 5.3% |
| win @ 3.00–5.00 | 326 | 27.3% | 25.7% | +1.6% | +1.1% ± 9.3% |
| win @ 5.00–1000.00 | 257 | 7.4% | 12.5% | -5.1% | -49.0% ± 11.7% |

### Competitions where a side stood out (30+ games, return two se or more from zero)

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| Japan · B League One — total:over | 63 | 41.3% | 50.1% | -8.8% | -24.7% ± 11.4% |
| Japan · B League One — win:away | 63 | 36.5% | 46.0% | -9.5% | -32.1% ± 13.2% |
| USA · NBA — win:home | 31 | 41.9% | 54.8% | -12.8% | -34.7% ± 14.4% |

### Covered by the board vs not

| | market | bets (every side) | landed − fair | £1 return |
|---|---|---|---|---|
| covered | hcp | 140 | +0.0% | -5.6% |
| not covered | hcp | 2186 | +0.0% | -7.3% |
| covered | total | 140 | +0.0% | -5.5% |
| not covered | total | 2184 | +0.0% | -7.3% |
| covered | win | 140 | +0.0% | -6.0% |
| not covered | win | 2180 | +0.0% | -9.5% |

### Price moves before kick-off (return at the FIRST price seen)

A side that shortened 3%+ between the first and last look — did backing it early pay?

| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |
|---|---|---|---|---|---|
| shortened 3%+ | 1049 | 50.3% | 50.4% | -0.1% | +2.2% ± 3.7% |
| steady | 4278 | 51.9% | 51.7% | +0.2% | -6.8% ± 1.4% |
| drifted 3%+ | 1155 | 42.5% | 43.2% | -0.7% | -19.4% ± 3.1% |

