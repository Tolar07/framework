# NBA MARKET STUDY — every SportyBet NBA market against the results

Each game's last look before tip-off, every outcome settled from ESPN's final and quarter scores. *Landed* = how often it won; *fair* = SportyBet's own chance (its prices, margin removed); *return* = £1 flat on every outcome at SportyBet's price. Landed above fair on a side = SportyBet under-prices it. Written by `backtest/nba_market_study.py`. A study, not a selector.

Games with a look: 185 · graded (ESPN final): 176

## Regular

| Market | outcomes | landed | fair | return | short side (<2.00): n · landed · fair · return | long side (≥2.00): n · landed · fair · return |
|---|---:|---:|---:|---:|---|---|
| Player points N+ | 28326 | 21.1% | 30.3% | -44.7% | 5922 · 53.9% · 64.8% · -16.8% | 22404 · 12.4% · 21.2% · -52.1% |
| Player rebounds N+ | 13369 | 23.0% | 30.5% | -37.6% | 2949 · 58.0% · 66.1% · -12.3% | 10420 · 13.1% · 20.4% · -44.8% |
| Player assists N+ | 8563 | 30.8% | 40.8% | -33.7% | 2882 · 62.9% · 73.6% · -15.1% | 5681 · 14.5% · 24.1% · -43.1% |
| Player 3-pointers N+ | 7277 | 18.8% | 27.1% | -47.8% | 1149 · 55.5% · 65.8% · -16.0% | 6128 · 11.9% · 19.8% · -53.8% |
| Total points (incl. OT) | 6642 | 50.0% | 50.0% | -3.6% | 3525 · 63.8% · 63.3% · -2.9% | 3117 · 34.4% · 35.0% · -4.3% |
| Handicap (incl. OT) | 6410 | 50.0% | 50.0% | -5.6% | 3352 · 68.9% · 67.7% · -2.4% | 3058 · 29.3% · 30.6% · -9.1% |
| Player points O/U | 3358 | 50.0% | 50.0% | -7.4% | 3262 · 50.1% · 50.1% · -7.5% | 96 · 46.9% · 45.7% · -4.7% |
| Player rebounds O/U | 3178 | 50.0% | 50.0% | -7.7% | 2256 · 53.1% · 52.3% · -6.3% | 922 · 42.5% · 44.3% · -11.2% |
| Player 3-pointers O/U | 2790 | 50.0% | 50.0% | -7.6% | 1737 · 55.6% · 55.1% · -6.7% | 1053 · 40.8% · 41.5% · -9.1% |
| 1st half total | 2702 | 50.0% | 50.0% | -4.4% | 1492 · 56.7% · 57.8% · -6.5% | 1210 · 41.7% · 40.4% · -1.7% |
| 1st half handicap | 2702 | 50.0% | 50.0% | -4.5% | 1492 · 57.7% · 58.3% · -5.7% | 1210 · 40.5% · 39.8% · -3.0% |
| Player assists O/U | 2638 | 50.0% | 50.0% | -7.9% | 1775 · 54.6% · 53.2% · -5.2% | 863 · 40.6% · 43.4% · -13.5% |
| 2nd half total (reg.) | 2552 | 50.0% | 50.0% | -5.5% | 1501 · 54.7% · 56.7% · -9.6% | 1051 · 43.3% · 40.4% · +0.5% |
| 2nd half handicap (reg.) | 2552 | 50.0% | 50.0% | -5.0% | 1408 · 58.9% · 58.7% · -4.5% | 1144 · 39.1% · 39.3% · -5.5% |
| Home team points (incl. OT) | 1230 | 50.0% | 50.0% | -4.9% | 754 · 53.6% · 53.3% · -4.3% | 476 · 44.3% · 44.8% · -5.8% |
| Away team points (incl. OT) | 1230 | 50.0% | 50.0% | -4.2% | 754 · 52.3% · 53.4% · -6.5% | 476 · 46.4% · 44.7% · -0.7% |
| Quarter handicap Q4 | 1230 | 50.0% | 50.0% | -4.0% | 712 · 53.5% · 55.1% · -7.3% | 518 · 45.2% · 43.0% · +0.6% |
| Quarter handicap Q3 | 1230 | 50.0% | 50.0% | -4.9% | 723 · 55.3% · 54.7% · -3.7% | 507 · 42.4% · 43.3% · -6.7% |
| Quarter handicap Q2 | 1230 | 50.0% | 50.0% | -4.6% | 729 · 53.6% · 54.6% · -6.4% | 501 · 44.7% · 43.3% · -1.9% |
| Quarter handicap Q1 | 1230 | 50.0% | 50.0% | -5.2% | 748 · 53.2% · 54.4% · -7.7% | 482 · 45.0% · 43.1% · -1.4% |
| Home team 1st half points | 1230 | 50.0% | 50.0% | -4.4% | 711 · 54.3% · 55.2% · -6.2% | 519 · 44.1% · 42.9% · -1.8% |
| Away team 1st half points | 1230 | 50.0% | 50.0% | -5.3% | 714 · 56.4% · 55.2% · -2.8% | 516 · 41.1% · 42.8% · -8.7% |
| Home team quarter points Q1 | 1230 | 50.0% | 50.0% | -4.9% | 698 · 56.0% · 57.3% · -7.7% | 532 · 42.1% · 40.4% · -1.2% |
| Away team quarter points Q1 | 1230 | 50.0% | 50.0% | -5.1% | 701 · 57.1% · 57.4% · -5.9% | 529 · 40.6% · 40.2% · -3.9% |
| Half time / full time | 1107 | 11.1% | 11.1% | -24.8% | 68 · 55.9% · 51.2% · -12.3% | 1039 · 8.2% · 8.5% · -25.6% |
| Quarter 1X2 Q1 | 369 | 33.3% | 33.3% | -7.3% | 129 · 51.9% · 55.2% · -13.0% | 240 · 23.3% · 21.6% · -4.2% |
| Quarter 1X2 Q2 | 369 | 33.3% | 33.3% | +1.3% | 131 · 53.4% · 53.1% · -6.7% | 238 · 22.3% · 22.5% · +5.7% |
| Quarter 1X2 Q3 | 369 | 33.3% | 33.3% | -9.9% | 132 · 59.8% · 54.4% · +2.0% | 237 · 18.6% · 21.6% · -16.5% |
| Quarter 1X2 Q4 | 369 | 33.3% | 33.3% | -1.4% | 133 · 51.1% · 50.8% · -6.1% | 236 · 23.3% · 23.5% · +1.3% |
| 1st half 1X2 | 369 | 33.3% | 33.3% | -3.2% | 128 · 60.9% · 58.2% · -1.2% | 241 · 18.7% · 20.1% · -4.4% |
| 1X2 (regulation) | 369 | 33.3% | 33.3% | -6.1% | 123 · 65.0% · 62.1% · -1.9% | 246 · 17.5% · 18.9% · -8.2% |
| 2nd half 1X2 (reg.) | 348 | 33.3% | 33.3% | -30.2% | 126 · 64.3% · 55.7% · +8.7% | 222 · 15.8% · 20.7% · -52.2% |
| Winner (incl. OT) | 246 | 50.0% | 50.0% | -10.4% | 128 · 68.8% · 65.0% · +2.0% | 118 · 29.7% · 33.7% · -23.9% |
| Quarter total Q3 | 246 | 50.0% | 50.0% | -4.8% | 227 · 50.7% · 50.2% · -3.9% | 19 · 42.1% · 47.7% · -15.8% |
| Quarter total Q1 | 246 | 50.0% | 50.0% | -5.7% | 246 · 50.0% · 50.0% · -5.7% | — |
| Quarter total Q2 | 246 | 50.0% | 50.0% | -4.7% | 231 · 48.9% · 50.1% · -7.1% | 15 · 66.7% · 47.8% · +33.3% |
| Total points (regulation) | 246 | 50.0% | 50.0% | -4.4% | 157 · 55.4% · 52.1% · +2.1% | 89 · 40.4% · 46.3% · -16.0% |
| Quarter odd/even Q1 | 246 | 50.0% | 50.0% | -5.0% | 246 · 50.0% · 50.0% · -5.0% | — |
| Quarter odd/even Q2 | 246 | 50.0% | 50.0% | -5.0% | 246 · 50.0% · 50.0% · -5.0% | — |
| Quarter odd/even Q3 | 246 | 50.0% | 50.0% | -5.0% | 246 · 50.0% · 50.0% · -5.0% | — |
| Quarter odd/even Q4 | 246 | 50.0% | 50.0% | -5.0% | 246 · 50.0% · 50.0% · -5.0% | — |
| Odd/even (incl. OT) | 246 | 50.0% | 50.0% | -4.9% | 246 · 50.0% · 50.0% · -4.9% | — |
| 1st half odd/even | 246 | 50.0% | 50.0% | -5.0% | 246 · 50.0% · 50.0% · -5.0% | — |
| Overtime yes/no | 244 | 50.0% | 50.0% | -13.5% | 122 · 94.3% · 92.4% · -2.8% | 122 · 5.7% · 7.6% · -24.2% |
| 1st half draw no bet | 236 | 50.0% | 50.0% | -4.5% | 127 · 62.2% · 60.1% · -0.9% | 109 · 35.8% · 38.2% · -8.8% |
| Quarter draw no bet Q1 | 234 | 50.0% | 50.0% | -4.1% | 134 · 52.2% · 57.4% · -14.0% | 100 · 47.0% · 40.1% · +9.1% |
| Quarter draw no bet Q3 | 234 | 50.0% | 50.0% | -6.1% | 134 · 62.7% · 56.9% · +5.3% | 100 · 33.0% · 40.8% · -21.5% |
| Draw no bet (regulation) | 232 | 50.0% | 50.0% | -11.5% | 125 · 67.2% · 64.1% · -0.8% | 107 · 29.9% · 33.5% · -23.9% |
| 2nd half odd/even (reg.) | 232 | 50.0% | 50.0% | -5.0% | 232 · 50.0% · 50.0% · -5.0% | — |
| Quarter draw no bet Q2 | 230 | 50.0% | 50.0% | -5.2% | 137 · 55.5% · 55.1% · -4.4% | 93 · 41.9% · 42.5% · -6.3% |
| Quarter draw no bet Q4 | 230 | 50.0% | 50.0% | -4.3% | 152 · 52.0% · 52.7% · -6.0% | 78 · 46.2% · 44.7% · -1.0% |
| 2nd half draw no bet (reg.) | 230 | 50.0% | 50.0% | -6.2% | 131 · 63.4% · 57.6% · +5.3% | 99 · 32.3% · 39.9% · -21.5% |
| 3-pointers made 1X2 | 213 | 33.3% | 33.3% | -23.1% | 74 · 62.2% · 57.1% · -2.8% | 139 · 18.0% · 20.7% · -34.0% |
| Assists 1X2 | 201 | 33.3% | 33.3% | -16.8% | 74 · 56.8% · 58.9% · -12.5% | 127 · 19.7% · 18.4% · -19.3% |
| Rebounds 1X2 | 201 | 33.3% | 33.3% | -25.1% | 76 · 52.6% · 58.6% · -19.6% | 125 · 21.6% · 18.0% · -28.5% |
| Quarter total Q4 | 172 | 50.0% | 50.0% | -4.4% | 151 · 48.3% · 50.3% · -8.4% | 21 · 61.9% · 47.7% · +23.8% |
| Team 3-pointers made total | 142 | 50.0% | 50.0% | -8.5% | 142 · 50.0% · 50.0% · -8.5% | — |
| Away 3-pointers made | 142 | 50.0% | 50.0% | -7.9% | 133 · 48.9% · 50.3% · -10.8% | 9 · 66.7% · 45.5% · +34.9% |
| Home 3-pointers made | 140 | 50.0% | 50.0% | -8.1% | 136 · 50.7% · 50.1% · -6.8% | 4 · 25.0% · 45.7% · -49.8% |
| Total assists | 134 | 50.0% | 50.0% | -8.4% | 134 · 50.0% · 50.0% · -8.4% | — |
| Home 2-pointers made | 132 | 50.0% | 50.0% | -8.6% | 132 · 50.0% · 50.0% · -8.6% | — |
| Away 2-pointers made | 132 | 50.0% | 50.0% | -8.0% | 132 · 50.0% · 50.0% · -8.0% | — |
| Team 2-pointers made total | 114 | 50.0% | 50.0% | -8.5% | 114 · 50.0% · 50.0% · -8.5% | — |
| Total rebounds | 88 | 50.0% | 50.0% | -8.6% | 88 · 50.0% · 50.0% · -8.6% | — |

## Preseason (starters rested — a weak test)

| Market | outcomes | landed | fair | return | short side (<2.00): n · landed · fair · return | long side (≥2.00): n · landed · fair · return |
|---|---:|---:|---:|---:|---|---|
| Total points (incl. OT) | 762 | 50.0% | 50.0% | -7.2% | 444 · 57.4% · 56.0% · -4.4% | 318 · 39.6% · 41.6% · -11.1% |
| Handicap (incl. OT) | 742 | 50.0% | 50.0% | -5.1% | 424 · 57.3% · 58.9% · -8.7% | 318 · 40.3% · 38.1% · -0.3% |
| Home team points (incl. OT) | 318 | 50.0% | 50.0% | -7.3% | 212 · 53.3% · 53.3% · -7.3% | 106 · 43.4% · 43.4% · -7.2% |
| Away team points (incl. OT) | 318 | 50.0% | 50.0% | -7.5% | 212 · 53.8% · 53.4% · -6.7% | 106 · 42.5% · 43.3% · -9.1% |
| Half time / full time | 189 | 11.1% | 11.1% | -41.4% | 12 · 58.3% · 49.1% · -6.3% | 177 · 7.9% · 8.5% · -43.8% |
| 1X2 (regulation) | 63 | 33.3% | 33.3% | +8.3% | 21 · 57.1% · 61.3% · -14.7% | 42 · 21.4% · 19.4% · +19.9% |
| Winner (incl. OT) | 42 | 50.0% | 50.0% | -4.3% | 23 · 56.5% · 63.1% · -16.3% | 19 · 42.1% · 34.2% · +10.3% |

## Would-be picks — the board's bars on every priced market (regular season)

Every outcome the sharp line prices (board markets and the SHADOW ones in engine/nba_value.SHADOW_MARKETS) that clears the board's bars at SportyBet's last recorded price before tip-off, graded. Several lines per game count (the board takes one); a backtest of the market, not of the board. SHADOW = priced and recorded only.

| Market | board / shadow | picks | won | stated chance | return ± se |
|---|---|---:|---:|---:|---|
| 1st half total | board | 740 | 62% | 68% | +3.5% ± 3.0% |
| 2nd half total (reg.) | board | 711 | 53% | 66% | -11.6% ± 3.2% |
| Home team 1st half points | board | 312 | 56% | 62% | -1.7% ± 5.0% |
| Away team 1st half points | board | 302 | 66% | 63% | +15.3% ± 4.8% |
| Home team quarter points Q1 | board | 125 | 62% | 62% | +5.8% ± 7.6% |
| Away team quarter points Q1 | board | 118 | 64% | 62% | +12.7% ± 7.9% |
| Quarter total Q3 | board | 99 | 52% | 59% | -2.2% ± 9.6% |
| Quarter total Q1 | board | 96 | 56% | 58% | +6.4% ± 9.6% |
| Quarter total Q2 | board | 68 | 51% | 60% | -2.1% ± 11.6% |
| Quarter total Q4 | board | 57 | 49% | 58% | -6.4% ± 12.7% |
| Quarter handicap Q2 | board | 17 | 59% | 60% | +3.5% ± 21.8% |
| Handicap (incl. OT) | board | 13 | 38% | 62% | -36.2% ± 23.4% |
| Quarter handicap Q3 | board | 6 | 50% | 62% | -11.5% ± 39.8% |
| 1st half handicap | board | 6 | 83% | 60% | +45.8% ± 29.9% |
| Quarter handicap Q4 | board | 5 | 100% | 59% | +82.2% ± 6.2% |

## Player props and team stat totals — Over vs Under (regular season)

| Market | side | outcomes | landed | fair | return |
|---|---|---:|---:|---:|---:|
| Away 2-pointers made | over | 66 | 43.9% | 49.8% | -18.7% |
| Away 2-pointers made | under | 66 | 56.1% | 50.2% | +2.7% |
| Away 3-pointers made | over | 71 | 46.5% | 49.7% | -13.9% |
| Away 3-pointers made | under | 71 | 53.5% | 50.3% | -1.9% |
| Home 2-pointers made | over | 66 | 43.9% | 49.8% | -19.3% |
| Home 2-pointers made | under | 66 | 56.1% | 50.2% | +2.2% |
| Home 3-pointers made | over | 70 | 50.0% | 49.7% | -7.6% |
| Home 3-pointers made | under | 70 | 50.0% | 50.3% | -8.5% |
| Player 3-pointers O/U | over | 1395 | 45.7% | 47.2% | -10.3% |
| Player 3-pointers O/U | under | 1395 | 54.3% | 52.8% | -4.9% |
| Player assists O/U | over | 1319 | 46.6% | 48.5% | -11.5% |
| Player assists O/U | under | 1319 | 53.4% | 51.5% | -4.4% |
| Player points O/U | over | 1679 | 48.0% | 49.7% | -10.6% |
| Player points O/U | under | 1679 | 52.0% | 50.3% | -4.2% |
| Player rebounds O/U | over | 1589 | 49.0% | 48.6% | -7.0% |
| Player rebounds O/U | under | 1589 | 51.0% | 51.4% | -8.4% |
| Team 2-pointers made total | over | 57 | 36.8% | 50.0% | -32.6% |
| Team 2-pointers made total | under | 57 | 63.2% | 50.0% | +15.6% |
| Team 3-pointers made total | over | 71 | 43.7% | 49.8% | -19.9% |
| Team 3-pointers made total | under | 71 | 56.3% | 50.2% | +2.9% |
| Total assists | over | 67 | 43.3% | 49.6% | -19.9% |
| Total assists | under | 67 | 56.7% | 50.4% | +3.1% |
| Total rebounds | over | 44 | 29.5% | 50.0% | -46.0% |
| Total rebounds | under | 44 | 70.5% | 50.0% | +28.9% |

## Seen, not settled (rule not confirmed — PENDING)

- 1st half draw no bet: 10 outcomes
- 2nd half 1X2 (reg.): 21 outcomes
- 2nd half draw no bet (reg.): 16 outcomes
- 2nd half handicap (reg.): 154 outcomes
- 2nd half odd/even (reg.): 14 outcomes
- 2nd half total (reg.): 154 outcomes
- Any team to lead by [967]: 732 outcomes
- Any team to win all quarters [1199]: 246 outcomes
- Any team to win both halves [1197]: 246 outcomes
- Any team total maximum consecutive points [964]: 246 outcomes
- Any team winning margin (incl. overtime) [849]: 791 outcomes
- Atlanta Hawks to lead by [965]: 18 outcomes
- Atlanta Hawks to lead by [966]: 36 outcomes
- Atlanta Hawks to win all quarters [1313]: 6 outcomes
- Atlanta Hawks to win all quarters [1314]: 12 outcomes
- Atlanta Hawks total maximum consecutive points [962]: 6 outcomes
- Atlanta Hawks total maximum consecutive points [963]: 12 outcomes
- Away Team to Win Both Halves [49]: 246 outcomes
- Boston Celtics to lead by [965]: 30 outcomes
- Boston Celtics to lead by [966]: 18 outcomes
- Boston Celtics to win all quarters [1313]: 10 outcomes
- Boston Celtics to win all quarters [1314]: 6 outcomes
- Boston Celtics total maximum consecutive points [962]: 10 outcomes
- Boston Celtics total maximum consecutive points [963]: 6 outcomes
- Brooklyn Nets to lead by [965]: 24 outcomes
- Brooklyn Nets to lead by [966]: 24 outcomes
- Brooklyn Nets to win all quarters [1313]: 8 outcomes
- Brooklyn Nets to win all quarters [1314]: 2 outcomes
- Brooklyn Nets total maximum consecutive points [962]: 8 outcomes
- Brooklyn Nets total maximum consecutive points [963]: 8 outcomes
- Charlotte Hornets to lead by [965]: 30 outcomes
- Charlotte Hornets to lead by [966]: 24 outcomes
- Charlotte Hornets to win all quarters [1313]: 10 outcomes
- Charlotte Hornets to win all quarters [1314]: 8 outcomes
- Charlotte Hornets total maximum consecutive points [962]: 10 outcomes
- Charlotte Hornets total maximum consecutive points [963]: 8 outcomes
- Chicago Bulls to lead by [965]: 12 outcomes
- Chicago Bulls to lead by [966]: 36 outcomes
- Chicago Bulls to win all quarters [1313]: 4 outcomes
- Chicago Bulls to win all quarters [1314]: 2 outcomes
- Chicago Bulls total maximum consecutive points [962]: 4 outcomes
- Chicago Bulls total maximum consecutive points [963]: 12 outcomes
- Cleveland Cavaliers to lead by [965]: 24 outcomes
- Cleveland Cavaliers to lead by [966]: 24 outcomes
- Cleveland Cavaliers to win all quarters [1313]: 8 outcomes
- Cleveland Cavaliers to win all quarters [1314]: 8 outcomes
- Cleveland Cavaliers total maximum consecutive points [962]: 8 outcomes
- Cleveland Cavaliers total maximum consecutive points [963]: 8 outcomes
- Dallas Mavericks to lead by [965]: 24 outcomes
- Dallas Mavericks to lead by [966]: 24 outcomes
- Dallas Mavericks to win all quarters [1313]: 6 outcomes
- Dallas Mavericks to win all quarters [1314]: 4 outcomes
- Dallas Mavericks total maximum consecutive points [962]: 8 outcomes
- Dallas Mavericks total maximum consecutive points [963]: 8 outcomes
- Denver Nuggets to lead by [965]: 24 outcomes
- Denver Nuggets to lead by [966]: 18 outcomes
- Denver Nuggets to win all quarters [1313]: 8 outcomes
- Denver Nuggets to win all quarters [1314]: 6 outcomes
- Denver Nuggets total maximum consecutive points [962]: 8 outcomes
- Denver Nuggets total maximum consecutive points [963]: 6 outcomes
- Detroit Pistons to lead by [965]: 18 outcomes
- Detroit Pistons to lead by [966]: 30 outcomes
- Detroit Pistons to win all quarters [1313]: 6 outcomes
- Detroit Pistons to win all quarters [1314]: 10 outcomes
- Detroit Pistons total maximum consecutive points [962]: 6 outcomes
- Detroit Pistons total maximum consecutive points [963]: 10 outcomes
- Draw no bet (regulation): 14 outcomes
- Golden State Warriors to lead by [965]: 30 outcomes
- Golden State Warriors to lead by [966]: 24 outcomes
- Golden State Warriors to win all quarters [1313]: 10 outcomes
- Golden State Warriors to win all quarters [1314]: 6 outcomes
- Golden State Warriors total maximum consecutive points [962]: 10 outcomes
- Golden State Warriors total maximum consecutive points [963]: 8 outcomes
- Handicap (including OT) & Total (including OT) [1174]: 492 outcomes
- Handicap : [14]: 369 outcomes
- Highest Scoring Half [52]: 231 outcomes
- Highest scoring quarter - Over/Under [1193]: 246 outcomes
- Highest scoring quarter [234]: 615 outcomes
- Home Team to Win Both Halves [48]: 246 outcomes
- Houston Rockets to lead by [965]: 30 outcomes
- Houston Rockets to lead by [966]: 24 outcomes
- Houston Rockets to win all quarters [1313]: 10 outcomes
- Houston Rockets to win all quarters [1314]: 8 outcomes
- Houston Rockets total maximum consecutive points [962]: 10 outcomes
- Houston Rockets total maximum consecutive points [963]: 8 outcomes
- Indiana Pacers to lead by [965]: 24 outcomes
- Indiana Pacers to lead by [966]: 30 outcomes
- Indiana Pacers to win all quarters [1313]: 6 outcomes
- Indiana Pacers to win all quarters [1314]: 10 outcomes
- Indiana Pacers total maximum consecutive points [962]: 8 outcomes
- Indiana Pacers total maximum consecutive points [963]: 10 outcomes
- LA Clippers to lead by [965]: 24 outcomes
- LA Clippers to lead by [966]: 24 outcomes
- LA Clippers to win all quarters [1313]: 8 outcomes
- LA Clippers to win all quarters [1314]: 4 outcomes
- LA Clippers total maximum consecutive points [962]: 8 outcomes
- LA Clippers total maximum consecutive points [963]: 8 outcomes
- Los Angeles Lakers to lead by [965]: 30 outcomes
- Los Angeles Lakers to lead by [966]: 24 outcomes
- Los Angeles Lakers to win all quarters [1313]: 10 outcomes
- Los Angeles Lakers to win all quarters [1314]: 8 outcomes
- Los Angeles Lakers total maximum consecutive points [962]: 10 outcomes
- Los Angeles Lakers total maximum consecutive points [963]: 8 outcomes
- Lowest scoring quarter - Over/Under [1195]: 246 outcomes
- Memphis Grizzlies to lead by [965]: 24 outcomes
- Memphis Grizzlies to lead by [966]: 24 outcomes
- Memphis Grizzlies to win all quarters [1313]: 8 outcomes
- Memphis Grizzlies to win all quarters [1314]: 8 outcomes
- Memphis Grizzlies total maximum consecutive points [962]: 8 outcomes
- Memphis Grizzlies total maximum consecutive points [963]: 8 outcomes
- Miami Heat to lead by [965]: 24 outcomes
- Miami Heat to lead by [966]: 30 outcomes
- Miami Heat to win all quarters [1313]: 8 outcomes
- Miami Heat to win all quarters [1314]: 10 outcomes
- Miami Heat total maximum consecutive points [962]: 8 outcomes
- Miami Heat total maximum consecutive points [963]: 10 outcomes
- Milwaukee Bucks to lead by [965]: 24 outcomes
- Milwaukee Bucks to lead by [966]: 24 outcomes
- Milwaukee Bucks to win all quarters [1313]: 4 outcomes
- Milwaukee Bucks to win all quarters [1314]: 2 outcomes
- Milwaukee Bucks total maximum consecutive points [962]: 8 outcomes
- Milwaukee Bucks total maximum consecutive points [963]: 8 outcomes
- Minnesota Timberwolves to lead by [965]: 24 outcomes
- Minnesota Timberwolves to lead by [966]: 30 outcomes
- Minnesota Timberwolves to win all quarters [1313]: 8 outcomes
- Minnesota Timberwolves to win all quarters [1314]: 8 outcomes
- Minnesota Timberwolves total maximum consecutive points [962]: 8 outcomes
- Minnesota Timberwolves total maximum consecutive points [963]: 10 outcomes
- New Orleans Pelicans to lead by [965]: 30 outcomes
- New Orleans Pelicans to lead by [966]: 18 outcomes
- New Orleans Pelicans to win all quarters [1313]: 10 outcomes
- New Orleans Pelicans to win all quarters [1314]: 4 outcomes
- New Orleans Pelicans total maximum consecutive points [962]: 10 outcomes
- New Orleans Pelicans total maximum consecutive points [963]: 6 outcomes
- New York Knicks to lead by [965]: 30 outcomes
- New York Knicks to lead by [966]: 18 outcomes
- New York Knicks to win all quarters [1313]: 10 outcomes
- New York Knicks to win all quarters [1314]: 6 outcomes
- New York Knicks total maximum consecutive points [962]: 10 outcomes
- New York Knicks total maximum consecutive points [963]: 6 outcomes
- Oklahoma City Thunder to lead by [965]: 24 outcomes
- Oklahoma City Thunder to lead by [966]: 24 outcomes
- Oklahoma City Thunder to win all quarters [1313]: 8 outcomes
- Oklahoma City Thunder to win all quarters [1314]: 8 outcomes
- Oklahoma City Thunder total maximum consecutive points [962]: 8 outcomes
- Oklahoma City Thunder total maximum consecutive points [963]: 8 outcomes
- Orlando Magic to lead by [965]: 24 outcomes
- Orlando Magic to lead by [966]: 24 outcomes
- Orlando Magic to win all quarters [1313]: 8 outcomes
- Orlando Magic to win all quarters [1314]: 6 outcomes
- Orlando Magic total maximum consecutive points [962]: 8 outcomes
- Orlando Magic total maximum consecutive points [963]: 8 outcomes
- Philadelphia ers to lead by [965]: 30 outcomes
- Philadelphia ers to lead by [966]: 24 outcomes
- Philadelphia ers to win all quarters [1313]: 10 outcomes
- Philadelphia ers to win all quarters [1314]: 8 outcomes
- Philadelphia ers total maximum consecutive points [962]: 10 outcomes
- Philadelphia ers total maximum consecutive points [963]: 8 outcomes
- Phoenix Suns to lead by [965]: 24 outcomes
- Phoenix Suns to lead by [966]: 18 outcomes
- Phoenix Suns to win all quarters [1313]: 8 outcomes
- Phoenix Suns to win all quarters [1314]: 4 outcomes
- Phoenix Suns total maximum consecutive points [962]: 8 outcomes
- Phoenix Suns total maximum consecutive points [963]: 6 outcomes
- Player 3-pointers N+: 46 outcomes
- Player 3-pointers O/U: 20 outcomes
- Player assists N+: 57 outcomes
- Player assists O/U: 20 outcomes
- Player points N+: 215 outcomes
- Player points O/U: 28 outcomes
- Player rebounds N+: 103 outcomes
- Player rebounds O/U: 24 outcomes
- Point range [298]: 1056 outcomes
- Portland Trail Blazers to lead by [965]: 12 outcomes
- Portland Trail Blazers to lead by [966]: 30 outcomes
- Portland Trail Blazers to win all quarters [1313]: 4 outcomes
- Portland Trail Blazers to win all quarters [1314]: 10 outcomes
- Portland Trail Blazers total maximum consecutive points [962]: 4 outcomes
- Portland Trail Blazers total maximum consecutive points [963]: 10 outcomes
- Quarter draw no bet Q1: 12 outcomes
- Quarter draw no bet Q2: 16 outcomes
- Quarter draw no bet Q3: 12 outcomes
- Quarter draw no bet Q4: 16 outcomes
- Race to  points (incl. overtime) [230]: 984 outcomes
- Sacramento Kings to lead by [965]: 18 outcomes
- Sacramento Kings to lead by [966]: 24 outcomes
- Sacramento Kings to win all quarters [1313]: 2 outcomes
- Sacramento Kings to win all quarters [1314]: 6 outcomes
- Sacramento Kings total maximum consecutive points [962]: 6 outcomes
- Sacramento Kings total maximum consecutive points [963]: 10 outcomes
- San Antonio Spurs to lead by [965]: 30 outcomes
- San Antonio Spurs to lead by [966]: 12 outcomes
- San Antonio Spurs to win all quarters [1313]: 12 outcomes
- San Antonio Spurs to win all quarters [1314]: 4 outcomes
- San Antonio Spurs total maximum consecutive points [962]: 12 outcomes
- San Antonio Spurs total maximum consecutive points [963]: 4 outcomes
- Smart Combo [820002]: 285 outcomes
- Team to win all quarters [1203]: 369 outcomes
- Team to win both halves [1201]: 369 outcomes
- Toronto Raptors to lead by [965]: 18 outcomes
- Toronto Raptors to lead by [966]: 30 outcomes
- Toronto Raptors to win all quarters [1313]: 6 outcomes
- Toronto Raptors to win all quarters [1314]: 10 outcomes
- Toronto Raptors total maximum consecutive points [962]: 6 outcomes
- Toronto Raptors total maximum consecutive points [963]: 10 outcomes
- Total (over-exact-under) [297]: 369 outcomes
- Utah Jazz to lead by [965]: 30 outcomes
- Utah Jazz to lead by [966]: 18 outcomes
- Utah Jazz to win all quarters [1313]: 8 outcomes
- Utah Jazz to win all quarters [1314]: 4 outcomes
- Utah Jazz total maximum consecutive points [962]: 10 outcomes
- Utah Jazz total maximum consecutive points [963]: 6 outcomes
- Washington Wizards to lead by [965]: 24 outcomes
- Washington Wizards to lead by [966]: 24 outcomes
- Washington Wizards to win all quarters [1313]: 8 outcomes
- Washington Wizards to win all quarters [1314]: 8 outcomes
- Washington Wizards total maximum consecutive points [962]: 8 outcomes
- Washington Wizards total maximum consecutive points [963]: 8 outcomes
- Winner & Over/Under (incl. overtime) [292]: 492 outcomes
- Winning margin (incl. overtime) [290]: 2403 outcomes
- X & Over/Under [37]: 738 outcomes
- nd quarter - last point [960]: 246 outcomes
- nd quarter - winning margin [301]: 339 outcomes
- rd quarter - winning margin [301]: 339 outcomes
- st free throw scored [961]: 246 outcomes
- st half handicap & st half total [1178]: 492 outcomes
- st half x & st half total [1177]: 738 outcomes
- st quarter - last point [960]: 246 outcomes
- st quarter - winning margin [301]: 339 outcomes
- st quarter handicap & st quarter total [1176]: 492 outcomes
- st quarter x & st quarter total [1175]: 738 outcomes
- th quarter - winning margin [301]: 339 outcomes
