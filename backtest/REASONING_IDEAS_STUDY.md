# REASONING IDEAS STUDY — 2026-10-27 19:30Z

To-do #7. 6440 graded football games from data/universe (72384 priced sides at SportyBet's first look); the later half starts at kick-off 2026-10-17T13:00Z. 931 graded board singles. Every threshold or map is chosen on the earlier half; the verdict reads the later half only. CLV MB = price taken x Matchbook's last fair chance - 1.

## Ideas 2 + 11 — calibration by market and league, bias checks

Flat 1-unit return of every side at SportyBet's first price (all games; ** = return above 2 se):

| market | fair band | n | landed | fair | return (both halves) |
|---|---|---|---|---|---|
| 1x2:away | 0%-20% | 1334 | 11.3% | 14.2% | -26.8% ± 5.9% |
| 1x2:away | 20%-40% | 3508 | 27.4% | 29.6% | -15.0% ± 2.4% |
| 1x2:away | 40%-60% | 1233 | 51.0% | 47.7% | -1.8% ± 2.8% |
| 1x2:away | 60%-80% | 320 | 75.6% | 67.7% | +3.1% ± 3.3% |
| 1x2:draw | 0%-20% | 824 | 12.0% | 16.2% | -31.1% ± 6.8% |
| 1x2:draw | 20%-40% | 5610 | 25.5% | 26.1% | -11.1% ± 2.0% |
| 1x2:home | 0%-20% | 485 | 13.2% | 14.0% | -8.9% ± 12.3% |
| 1x2:home | 20%-40% | 2327 | 33.0% | 32.1% | -6.2% ± 2.8% |
| 1x2:home | 40%-60% | 2690 | 50.9% | 48.8% | -4.4% ± 1.8% |
| 1x2:home | 60%-80% | 845 | 72.2% | 67.6% | -1.6% ± 2.1% |
| btts:no | 20%-40% | 1040 | 37.1% | 35.9% | -5.0% ± 3.9% |
| btts:no | 40%-60% | 3291 | 45.2% | 48.0% | -13.8% ± 1.7% |
| btts:yes | 40%-60% | 3283 | 54.6% | 51.9% | -3.6% ± 1.5% |
| btts:yes | 60%-80% | 1060 | 62.8% | 64.1% | -10.0% ± 2.1% |
| dc:12 | 20%-40% | 5269 | 74.9% | 36.6% | -5.7% ± 0.8% |
| dc:12 | 40%-60% | 585 | 89.7% | 41.7% | -0.5% ± 1.4% |
| dc:1x | 0%-20% | 247 | 21.1% | 16.4% | -38.4% ± 8.0% |
| dc:1x | 20%-40% | 4677 | 66.9% | 33.2% | -7.7% ± 1.0% |
| dc:1x | 40%-60% | 930 | 89.0% | 42.2% | -2.5% ± 1.1% |
| dc:x2 | 0%-20% | 632 | 23.4% | 16.2% | -35.2% ± 4.7% |
| dc:x2 | 20%-40% | 4889 | 57.0% | 29.7% | -12.2% ± 1.1% |
| dc:x2 | 40%-60% | 333 | 87.4% | 42.2% | -4.2% ± 2.0% |
| ou1.5:over | 60%-80% | 3122 | 75.5% | 72.7% | -3.7% ± 1.0% |
| ou1.5:over | 80%-100% | 711 | 85.2% | 83.0% | -3.7% ± 1.5% |
| ou1.5:under | 0%-20% | 711 | 14.8% | 17.0% | -19.8% ± 7.3% |
| ou1.5:under | 20%-40% | 3122 | 24.5% | 27.3% | -17.4% ± 2.7% |
| ou2.5:over | 20%-40% | 315 | 39.4% | 36.1% | -0.4% ± 7.0% |
| ou2.5:over | 40%-60% | 3259 | 53.2% | 50.9% | -3.7% ± 1.6% |
| ou2.5:over | 60%-80% | 1256 | 67.7% | 65.7% | -4.5% ± 1.9% |
| ou2.5:under | 20%-40% | 1256 | 32.3% | 34.3% | -13.4% ± 3.6% |
| ou2.5:under | 40%-60% | 3259 | 46.8% | 49.1% | -12.4% ± 1.7% |
| ou2.5:under | 60%-80% | 315 | 60.6% | 63.9% | -12.7% ± 4.0% |
| ou3.5:over | 20%-40% | 3029 | 32.1% | 31.1% | -5.2% ± 2.6% |
| ou3.5:over | 40%-60% | 1332 | 47.1% | 46.1% | -6.0% ± 2.8% |
| ou3.5:under | 40%-60% | 1332 | 52.9% | 53.9% | -9.3% ± 2.4% |
| ou3.5:under | 60%-80% | 3029 | 67.9% | 68.9% | -8.8% ± 1.1% |

**Calibrated by market** (threshold 8%): earlier n 95, hit 47.4%, return +15.4% ± 12.9%, CLV SB -0.3%, CLV MB -4.3% (n 2); later **n 123, hit 34.1%, return -14.5% ± 10.9%, CLV SB -0.8%, CLV MB -6.5% (n 65)**

**Calibrated by league** (threshold 2%): earlier no bets; later **no bets**

## Idea 5 — cross-market consistency inside SportyBet

Poisson goals fitted to SportyBet's own 1X2 + Over/Under 2.5 (margin removed); bet O/U 1.5, O/U 3.5 and BTTS when SportyBet's price beats the implied chance. Double chance read straight from the 1X2.

**Poisson O/U 1.5/3.5 + BTTS** (threshold 2%): earlier n 5, hit 0.0%, return -100.0% ± 0.0%, CLV SB +9.9%, CLV MB —; later **n 3, hit 66.7%, return +76.7% ± 89.5%, CLV SB +18.3%, CLV MB +37.4% (n 1)**

**1X2-implied double chance** (threshold 2%): earlier no bets; later **no bets**

## Ideas 4 + 17 — timing, steam, price shopping

1X2 log loss on 1505 games both books priced (lower is better):

- SportyBet first: 0.9976
- SportyBet last: 0.9894
- Matchbook first: 0.9909
- Matchbook last: 0.9880

**Follow Matchbook steam at SportyBet's last price** (threshold 1%): earlier n 11, hit 27.3%, return -44.0% ± 30.6%, CLV SB —, CLV MB +5.9% (n 11); later **n 84, hit 42.9%, return -0.6% ± 13.9%, CLV SB —, CLV MB +3.5% (n 84)**

**Price-shop at the close (SportyBet last vs Matchbook last fair)** (threshold 2%): earlier n 7, hit 14.3%, return -58.6% ± 41.4%, CLV SB —, CLV MB +28.8% (n 7); later **n 77, hit 41.6%, return +11.6% ± 17.0%, CLV SB —, CLV MB +11.9% (n 77)**

**H001 entry time** (later half): at the first price n 475, hit 37.3%, return +17.9% ± 9.0%, CLV SB +15.5%, CLV MB +8.1% (n 474); at the last price n 475, hit 37.3%, return +1.4% ± 7.4%, CLV SB —, CLV MB +8.1% (n 474)

## Idea 9 — Kelly shrunk by model disagreement (board singles)

Terciles from the earlier half: gap ≤ +0.011 | ≤ +0.027 | above.

| gap band | earlier half | later half |
|---|---|---|
| low | n 156, hit 73.7%, return -9.4% ± 4.4%, CLV SB -0.3%, CLV MB — | n 91, hit 73.6%, return -10.1% ± 5.7%, CLV SB -0.1%, CLV MB — |
| mid | n 155, hit 81.9%, return +1.3% ± 3.8%, CLV SB +0.0%, CLV MB — | n 51, hit 72.5%, return -10.8% ± 7.8%, CLV SB +0.0%, CLV MB — |
| high | n 154, hit 76.0%, return -3.9% ± 4.4%, CLV SB +0.3%, CLV MB — | n 324, hit 76.5%, return -2.7% ± 3.0%, CLV SB +0.3%, CLV MB — |

Later half, same total stake: flat -5.02% per unit, stake shrunk by disagreement -7.47% per unit.

## Idea 15 — drift detection (board singles)

Chosen on the earlier half: k = 0.02, h = 2.0.
Earlier half: with the alarm -3.22% per pick vs flat -3.98% (6 alarms, 296 picks at half stake).
Later half: with the alarm -3.11% per pick vs flat -5.02% (3 alarms, 390 picks at half stake); gain +1.91% ± 1.15% per pick.

## Ideas 8 + 16 — correlation of picks and accas, exposure caps

- same league, same day: 3567 pairs, residual covariance +0.0073 ± 0.0031
- different league, same day: 31161 pairs, residual covariance +0.0026 ± 0.0011
- accas: 141 graded, landed 33.3% vs stated 40.3%
- acca chance x 1.02 (fitted on the earlier 70): later-half Brier 0.2344 -> 0.2375; later landed 29.6% vs stated 44.1%

Cap chosen on the earlier half: 4 pick(s) per league per day.
- earlier: inside the cap n 319, hit 77.7%, return -3.4% ± 2.9%, CLV SB +0.2%, CLV MB —; past it n 146, hit 76.0%, return -5.2% ± 4.4%, CLV SB -0.4%, CLV MB —
- later: inside the cap **n 327, hit 78.3%, return -1.6% ± 2.9%, CLV SB +0.2%, CLV MB —**; past it **n 139, hit 69.1%, return -13.1% ± 5.0%, CLV SB +0.0%, CLV MB —**

## Verdicts (later half)

| idea | verdict | later half |
|---|---|---|
| calibration by market | LOSE | n 123, hit 34.1%, return -14.5% ± 10.9%, CLV SB -0.8%, CLV MB -6.5% (n 65) |
| calibration by league | LOSE | no bets |
| cross-market: Poisson O/U 1.5/3.5 + BTTS | LOSE | n 3, hit 66.7%, return +76.7% ± 89.5%, CLV SB +18.3%, CLV MB +37.4% (n 1) |
| cross-market: 1X2-implied double chance | LOSE | no bets |
| Follow Matchbook steam at SportyBet's last price | LOSE | n 84, hit 42.9%, return -0.6% ± 13.9%, CLV SB —, CLV MB +3.5% (n 84) |
| Price-shop at the close (SportyBet last vs Matchbook last fair) | LOSE | n 77, hit 41.6%, return +11.6% ± 17.0%, CLV SB —, CLV MB +11.9% (n 77) |
