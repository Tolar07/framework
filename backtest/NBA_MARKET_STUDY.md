# NBA MARKET STUDY — every SportyBet NBA market against the results

Each game's last look before tip-off, every outcome settled from ESPN's final and quarter scores. *Landed* = how often it won; *fair* = SportyBet's own chance (its prices, margin removed); *return* = £1 flat on every outcome at SportyBet's price. Landed above fair on a side = SportyBet under-prices it. Written by `backtest/nba_market_study.py`. A study, not a selector.

Games with a look: 176 · graded (ESPN final): 174

## Regular

| Market | outcomes | landed | fair | return | short side (<2.00): n · landed · fair · return | long side (≥2.00): n · landed · fair · return |
|---|---:|---:|---:|---:|---|---|
| Player points N+ | 27871 | 21.1% | 5.9% | -44.8% | 5827 · 54.0% · 12.6% · -16.7% | 22044 · 12.4% · 4.2% · -52.2% |
| Player rebounds N+ | 13141 | 23.0% | 11.9% | -37.8% | 2898 · 57.9% · 24.8% · -12.4% | 10243 · 13.1% · 8.2% · -45.0% |
| Player assists N+ | 8405 | 30.7% | 15.5% | -33.9% | 2826 · 62.7% · 26.3% · -15.3% | 5579 · 14.4% · 10.0% · -43.4% |
| Player 3-pointers N+ | 7158 | 18.8% | 19.2% | -47.8% | 1128 · 55.4% · 37.9% · -16.2% | 6030 · 11.9% · 15.7% · -53.7% |
| Total points (incl. OT) | 6534 | 50.0% | 50.0% | -3.5% | 3468 · 63.7% · 63.3% · -3.1% | 3066 · 34.5% · 35.0% · -4.0% |
| Handicap (incl. OT) | 6306 | 50.0% | 50.0% | -5.9% | 3298 · 69.1% · 67.7% · -2.0% | 3008 · 29.0% · 30.6% · -10.2% |
| Player points O/U | 3302 | 50.0% | 50.0% | -7.4% | 3208 · 50.1% · 50.1% · -7.4% | 94 · 46.8% · 45.7% · -4.9% |
| Player rebounds O/U | 3124 | 50.0% | 50.0% | -7.7% | 2219 · 53.0% · 52.3% · -6.3% | 905 · 42.5% · 44.3% · -11.1% |
| Player 3-pointers O/U | 2744 | 50.0% | 50.0% | -7.6% | 1708 · 55.5% · 55.1% · -6.8% | 1036 · 40.9% · 41.5% · -8.9% |
| 1st half total | 2658 | 50.0% | 50.0% | -4.3% | 1468 · 56.5% · 57.8% · -6.9% | 1190 · 42.0% · 40.4% · -1.0% |
| 1st half handicap | 2658 | 50.0% | 50.0% | -4.4% | 1467 · 57.6% · 58.3% · -5.9% | 1191 · 40.6% · 39.8% · -2.7% |
| Player assists O/U | 2590 | 50.0% | 50.0% | -7.9% | 1743 · 54.6% · 53.2% · -5.3% | 847 · 40.6% · 43.4% · -13.4% |
| 2nd half total (reg.) | 2508 | 50.0% | 50.0% | -5.2% | 1476 · 54.1% · 56.7% · -10.5% | 1032 · 44.1% · 40.4% · +2.4% |
| 2nd half handicap (reg.) | 2508 | 50.0% | 50.0% | -4.9% | 1384 · 58.7% · 58.7% · -4.9% | 1124 · 39.3% · 39.3% · -4.9% |
| Home team points (incl. OT) | 1210 | 50.0% | 50.0% | -4.8% | 742 · 53.4% · 53.3% · -4.7% | 468 · 44.7% · 44.8% · -5.1% |
| Away team points (incl. OT) | 1210 | 50.0% | 50.0% | -4.2% | 742 · 52.3% · 53.4% · -6.4% | 468 · 46.4% · 44.7% · -0.8% |
| Quarter handicap Q4 | 1210 | 50.0% | 50.0% | -4.0% | 700 · 53.6% · 55.1% · -7.2% | 510 · 45.1% · 43.0% · +0.4% |
| Quarter handicap Q3 | 1210 | 50.0% | 50.0% | -5.0% | 711 · 55.4% · 54.7% · -3.6% | 499 · 42.3% · 43.3% · -7.0% |
| Quarter handicap Q2 | 1210 | 50.0% | 50.0% | -4.6% | 717 · 53.7% · 54.6% · -6.3% | 493 · 44.6% · 43.3% · -2.1% |
| Quarter handicap Q1 | 1210 | 50.0% | 50.0% | -5.2% | 736 · 53.3% · 54.4% · -7.6% | 474 · 44.9% · 43.1% · -1.6% |
| Home team 1st half points | 1210 | 50.0% | 50.0% | -4.4% | 699 · 54.4% · 55.2% · -6.1% | 511 · 44.0% · 42.9% · -2.0% |
| Away team 1st half points | 1210 | 50.0% | 50.0% | -5.3% | 703 · 56.5% · 55.2% · -2.8% | 507 · 41.0% · 42.8% · -8.8% |
| Home team quarter points Q1 | 1210 | 50.0% | 50.0% | -4.8% | 688 · 56.0% · 57.3% · -7.7% | 522 · 42.1% · 40.3% · -1.1% |
| Away team quarter points Q1 | 1210 | 50.0% | 50.0% | -5.0% | 690 · 57.0% · 57.4% · -6.1% | 520 · 40.8% · 40.2% · -3.6% |
| Half time / full time | 1089 | 11.1% | 11.1% | -27.5% | 68 · 55.9% · 51.2% · -12.3% | 1021 · 8.1% · 8.4% · -28.5% |
| Quarter 1X2 Q1 | 363 | 33.3% | 33.3% | -6.9% | 127 · 52.0% · 55.3% · -13.1% | 236 · 23.3% · 21.5% · -3.5% |
| Quarter 1X2 Q2 | 363 | 33.3% | 33.3% | +1.9% | 129 · 52.7% · 53.1% · -8.2% | 234 · 22.6% · 22.4% · +7.5% |
| Quarter 1X2 Q3 | 363 | 33.3% | 33.3% | -9.4% | 130 · 59.2% · 54.5% · +0.8% | 233 · 18.9% · 21.5% · -15.1% |
| Quarter 1X2 Q4 | 363 | 33.3% | 33.3% | -0.8% | 131 · 51.1% · 50.8% · -6.1% | 232 · 23.3% · 23.5% · +2.2% |
| 1st half 1X2 | 363 | 33.3% | 33.3% | -8.8% | 126 · 61.1% · 58.3% · -1.1% | 237 · 18.6% · 20.1% · -12.9% |
| 1X2 (regulation) | 363 | 33.3% | 33.3% | -5.5% | 121 · 64.5% · 62.3% · -3.2% | 242 · 17.8% · 18.9% · -6.7% |
| 2nd half 1X2 (reg.) | 342 | 33.3% | 33.3% | -30.0% | 124 · 63.7% · 55.7% · +7.6% | 218 · 16.1% · 20.6% · -51.4% |
| Winner (incl. OT) | 242 | 50.0% | 50.0% | -10.4% | 126 · 68.3% · 65.2% · +0.9% | 116 · 30.2% · 33.5% · -22.6% |
| Quarter total Q3 | 242 | 50.0% | 50.0% | -4.8% | 223 · 50.7% · 50.2% · -3.9% | 19 · 42.1% · 47.7% · -15.8% |
| Quarter total Q1 | 242 | 50.0% | 50.0% | -5.7% | 242 · 50.0% · 50.0% · -5.7% | — |
| Quarter total Q2 | 242 | 50.0% | 50.0% | -4.6% | 228 · 48.7% · 50.1% · -7.6% | 14 · 71.4% · 47.8% · +42.9% |
| Total points (regulation) | 242 | 50.0% | 50.0% | -4.4% | 154 · 55.2% · 52.2% · +1.7% | 88 · 40.9% · 46.2% · -15.0% |
| Quarter odd/even Q1 | 242 | 50.0% | 50.0% | -5.0% | 242 · 50.0% · 50.0% · -5.0% | — |
| Quarter odd/even Q2 | 242 | 50.0% | 50.0% | -5.0% | 242 · 50.0% · 50.0% · -5.0% | — |
| Quarter odd/even Q3 | 242 | 50.0% | 50.0% | -5.0% | 242 · 50.0% · 50.0% · -5.0% | — |
| Quarter odd/even Q4 | 242 | 50.0% | 50.0% | -5.0% | 242 · 50.0% · 50.0% · -5.0% | — |
| Odd/even (incl. OT) | 242 | 50.0% | 50.0% | -4.9% | 242 · 50.0% · 50.0% · -4.9% | — |
| 1st half odd/even | 242 | 50.0% | 50.0% | -5.0% | 242 · 50.0% · 50.0% · -5.0% | — |
| Overtime yes/no | 240 | 50.0% | 50.0% | -12.9% | 120 · 94.2% · 92.4% · -2.9% | 120 · 5.8% · 7.6% · -22.9% |
| 1st half draw no bet | 234 | 50.0% | 50.0% | -4.5% | 125 · 62.4% · 60.3% · -0.8% | 109 · 35.8% · 38.2% · -8.8% |
| Quarter draw no bet Q1 | 230 | 50.0% | 50.0% | -4.2% | 131 · 52.7% · 57.5% · -13.4% | 99 · 46.5% · 40.0% · +8.0% |
| Quarter draw no bet Q3 | 230 | 50.0% | 50.0% | -6.1% | 131 · 62.6% · 57.0% · +5.0% | 99 · 33.3% · 40.7% · -20.7% |
| Draw no bet (regulation) | 228 | 50.0% | 50.0% | -11.4% | 123 · 66.7% · 64.3% · -2.0% | 105 · 30.5% · 33.3% · -22.4% |
| 2nd half odd/even (reg.) | 228 | 50.0% | 50.0% | -5.0% | 228 · 50.0% · 50.0% · -5.0% | — |
| Quarter draw no bet Q2 | 226 | 50.0% | 50.0% | -5.1% | 134 · 55.2% · 55.2% · -5.0% | 92 · 42.4% · 42.4% · -5.3% |
| Quarter draw no bet Q4 | 226 | 50.0% | 50.0% | -4.3% | 149 · 51.7% · 52.8% · -6.7% | 77 · 46.8% · 44.7% · +0.3% |
| 2nd half draw no bet (reg.) | 226 | 50.0% | 50.0% | -6.1% | 128 · 63.3% · 57.7% · +5.0% | 98 · 32.7% · 39.9% · -20.7% |
| 3-pointers made 1X2 | 207 | 33.3% | 33.3% | -22.6% | 72 · 62.5% · 57.0% · -1.8% | 135 · 17.8% · 20.7% · -33.7% |
| Assists 1X2 | 198 | 33.3% | 33.3% | -16.4% | 73 · 56.2% · 58.9% · -13.5% | 125 · 20.0% · 18.4% · -18.0% |
| Rebounds 1X2 | 198 | 33.3% | 33.3% | -25.0% | 74 · 52.7% · 58.8% · -20.1% | 124 · 21.8% · 18.1% · -27.9% |
| Quarter total Q4 | 170 | 50.0% | 50.0% | -4.4% | 149 · 48.3% · 50.3% · -8.4% | 21 · 61.9% · 47.7% · +23.8% |
| Team 3-pointers made total | 138 | 50.0% | 50.0% | -8.4% | 138 · 50.0% · 50.0% · -8.4% | — |
| Home 3-pointers made | 138 | 50.0% | 50.0% | -8.1% | 134 · 50.7% · 50.1% · -6.8% | 4 · 25.0% · 45.7% · -49.8% |
| Away 3-pointers made | 138 | 50.0% | 50.0% | -7.8% | 130 · 48.5% · 50.3% · -11.4% | 8 · 75.0% · 45.5% · +51.7% |
| Total assists | 132 | 50.0% | 50.0% | -8.5% | 132 · 50.0% · 50.0% · -8.5% | — |
| Home 2-pointers made | 128 | 50.0% | 50.0% | -8.6% | 128 · 50.0% · 50.0% · -8.6% | — |
| Away 2-pointers made | 128 | 50.0% | 50.0% | -8.1% | 128 · 50.0% · 50.0% · -8.1% | — |
| Team 2-pointers made total | 110 | 50.0% | 50.0% | -8.6% | 110 · 50.0% · 50.0% · -8.6% | — |
| Total rebounds | 86 | 50.0% | 50.0% | -8.6% | 86 · 50.0% · 50.0% · -8.6% | — |

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
| 1st half total | board | 727 | 62% | 68% | +2.3% ± 3.0% |
| 2nd half total (reg.) | shadow | 697 | 52% | 66% | -12.7% ± 3.2% |
| Home team 1st half points | shadow | 306 | 56% | 62% | -1.5% ± 5.0% |
| Away team 1st half points | shadow | 295 | 65% | 63% | +13.9% ± 4.9% |
| Home team quarter points Q1 | shadow | 121 | 61% | 62% | +5.3% ± 7.8% |
| Away team quarter points Q1 | shadow | 115 | 63% | 62% | +10.7% ± 8.0% |
| Quarter total Q3 | shadow | 97 | 51% | 59% | -4.1% ± 9.7% |
| Quarter total Q1 | board | 94 | 56% | 58% | +6.7% ± 9.7% |
| Quarter total Q2 | shadow | 67 | 51% | 60% | -3.3% ± 11.7% |
| Quarter total Q4 | shadow | 57 | 49% | 58% | -6.4% ± 12.7% |
| Quarter handicap Q2 | board | 17 | 59% | 60% | +3.5% ± 21.8% |
| Handicap (incl. OT) | board | 13 | 38% | 62% | -36.2% ± 23.4% |
| Quarter handicap Q3 | board | 6 | 50% | 62% | -11.5% ± 39.8% |
| 1st half handicap | board | 6 | 83% | 60% | +45.8% ± 29.9% |
| Quarter handicap Q4 | shadow | 5 | 100% | 59% | +82.2% ± 6.2% |

## Player props and team stat totals — Over vs Under (regular season)

| Market | side | outcomes | landed | fair | return |
|---|---|---:|---:|---:|---:|
| Away 2-pointers made | over | 64 | 43.8% | 49.8% | -19.2% |
| Away 2-pointers made | under | 64 | 56.2% | 50.2% | +3.0% |
| Away 3-pointers made | over | 69 | 46.4% | 49.7% | -13.9% |
| Away 3-pointers made | under | 69 | 53.6% | 50.3% | -1.6% |
| Home 2-pointers made | over | 64 | 43.8% | 49.9% | -19.8% |
| Home 2-pointers made | under | 64 | 56.2% | 50.1% | +2.7% |
| Home 3-pointers made | over | 69 | 49.3% | 49.7% | -8.9% |
| Home 3-pointers made | under | 69 | 50.7% | 50.3% | -7.2% |
| Player 3-pointers O/U | over | 1372 | 45.7% | 47.1% | -10.3% |
| Player 3-pointers O/U | under | 1372 | 54.3% | 52.9% | -4.9% |
| Player assists O/U | over | 1295 | 46.5% | 48.5% | -11.7% |
| Player assists O/U | under | 1295 | 53.5% | 51.5% | -4.2% |
| Player points O/U | over | 1651 | 48.1% | 49.7% | -10.4% |
| Player points O/U | under | 1651 | 51.9% | 50.3% | -4.3% |
| Player rebounds O/U | over | 1562 | 49.1% | 48.7% | -6.9% |
| Player rebounds O/U | under | 1562 | 50.9% | 51.3% | -8.5% |
| Team 2-pointers made total | over | 55 | 38.2% | 50.0% | -30.2% |
| Team 2-pointers made total | under | 55 | 61.8% | 50.0% | +13.0% |
| Team 3-pointers made total | over | 69 | 43.5% | 49.9% | -20.2% |
| Team 3-pointers made total | under | 69 | 56.5% | 50.1% | +3.4% |
| Total assists | over | 66 | 42.4% | 49.6% | -21.6% |
| Total assists | under | 66 | 57.6% | 50.4% | +4.7% |
| Total rebounds | over | 43 | 30.2% | 50.0% | -44.8% |
| Total rebounds | under | 43 | 69.8% | 50.0% | +27.6% |

## Seen, not settled (rule not confirmed — PENDING)

- 1st half draw no bet: 8 outcomes
- 2nd half 1X2 (reg.): 21 outcomes
- 2nd half draw no bet (reg.): 16 outcomes
- 2nd half handicap (reg.): 154 outcomes
- 2nd half odd/even (reg.): 14 outcomes
- 2nd half total (reg.): 154 outcomes
- Any team to lead by [967]: 720 outcomes
- Any team to win all quarters [1199]: 242 outcomes
- Any team to win both halves [1197]: 242 outcomes
- Any team total maximum consecutive points [964]: 242 outcomes
- Any team winning margin (incl. overtime) [849]: 777 outcomes
- Atlanta Hawks to lead by [965]: 18 outcomes
- Atlanta Hawks to lead by [966]: 36 outcomes
- Atlanta Hawks to win all quarters [1313]: 6 outcomes
- Atlanta Hawks to win all quarters [1314]: 12 outcomes
- Atlanta Hawks total maximum consecutive points [962]: 6 outcomes
- Atlanta Hawks total maximum consecutive points [963]: 12 outcomes
- Away Team to Win Both Halves [49]: 242 outcomes
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
- Golden State Warriors to lead by [965]: 24 outcomes
- Golden State Warriors to lead by [966]: 24 outcomes
- Golden State Warriors to win all quarters [1313]: 8 outcomes
- Golden State Warriors to win all quarters [1314]: 6 outcomes
- Golden State Warriors total maximum consecutive points [962]: 8 outcomes
- Golden State Warriors total maximum consecutive points [963]: 8 outcomes
- Handicap (including OT) & Total (including OT) [1174]: 484 outcomes
- Handicap : [14]: 363 outcomes
- Highest Scoring Half [52]: 228 outcomes
- Highest scoring quarter - Over/Under [1193]: 242 outcomes
- Highest scoring quarter [234]: 605 outcomes
- Home Team to Win Both Halves [48]: 242 outcomes
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
- Lowest scoring quarter - Over/Under [1195]: 242 outcomes
- Memphis Grizzlies to lead by [965]: 24 outcomes
- Memphis Grizzlies to lead by [966]: 24 outcomes
- Memphis Grizzlies to win all quarters [1313]: 8 outcomes
- Memphis Grizzlies to win all quarters [1314]: 8 outcomes
- Memphis Grizzlies total maximum consecutive points [962]: 8 outcomes
- Memphis Grizzlies total maximum consecutive points [963]: 8 outcomes
- Miami Heat to lead by [965]: 24 outcomes
- Miami Heat to lead by [966]: 24 outcomes
- Miami Heat to win all quarters [1313]: 8 outcomes
- Miami Heat to win all quarters [1314]: 8 outcomes
- Miami Heat total maximum consecutive points [962]: 8 outcomes
- Miami Heat total maximum consecutive points [963]: 8 outcomes
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
- Orlando Magic to lead by [966]: 18 outcomes
- Orlando Magic to win all quarters [1313]: 8 outcomes
- Orlando Magic to win all quarters [1314]: 4 outcomes
- Orlando Magic total maximum consecutive points [962]: 8 outcomes
- Orlando Magic total maximum consecutive points [963]: 6 outcomes
- Philadelphia ers to lead by [965]: 30 outcomes
- Philadelphia ers to lead by [966]: 24 outcomes
- Philadelphia ers to win all quarters [1313]: 10 outcomes
- Philadelphia ers to win all quarters [1314]: 8 outcomes
- Philadelphia ers total maximum consecutive points [962]: 10 outcomes
- Philadelphia ers total maximum consecutive points [963]: 8 outcomes
- Phoenix Suns to lead by [965]: 18 outcomes
- Phoenix Suns to lead by [966]: 18 outcomes
- Phoenix Suns to win all quarters [1313]: 6 outcomes
- Phoenix Suns to win all quarters [1314]: 4 outcomes
- Phoenix Suns total maximum consecutive points [962]: 6 outcomes
- Phoenix Suns total maximum consecutive points [963]: 6 outcomes
- Player 3-pointers N+: 46 outcomes
- Player 3-pointers O/U: 20 outcomes
- Player assists N+: 57 outcomes
- Player assists O/U: 20 outcomes
- Player points N+: 215 outcomes
- Player points O/U: 28 outcomes
- Player rebounds N+: 103 outcomes
- Player rebounds O/U: 24 outcomes
- Point range [298]: 1044 outcomes
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
- Race to  points (incl. overtime) [230]: 968 outcomes
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
- Smart Combo [820002]: 275 outcomes
- Team to win all quarters [1203]: 363 outcomes
- Team to win both halves [1201]: 363 outcomes
- Toronto Raptors to lead by [965]: 18 outcomes
- Toronto Raptors to lead by [966]: 30 outcomes
- Toronto Raptors to win all quarters [1313]: 6 outcomes
- Toronto Raptors to win all quarters [1314]: 10 outcomes
- Toronto Raptors total maximum consecutive points [962]: 6 outcomes
- Toronto Raptors total maximum consecutive points [963]: 10 outcomes
- Total (over-exact-under) [297]: 363 outcomes
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
- Winner & Over/Under (incl. overtime) [292]: 484 outcomes
- Winning margin (incl. overtime) [290]: 2361 outcomes
- X & Over/Under [37]: 726 outcomes
- nd quarter - last point [960]: 242 outcomes
- nd quarter - winning margin [301]: 333 outcomes
- rd quarter - winning margin [301]: 333 outcomes
- st free throw scored [961]: 242 outcomes
- st half handicap & st half total [1178]: 484 outcomes
- st half x & st half total [1177]: 726 outcomes
- st quarter - last point [960]: 242 outcomes
- st quarter - winning margin [301]: 333 outcomes
- st quarter handicap & st quarter total [1176]: 484 outcomes
- st quarter x & st quarter total [1175]: 726 outcomes
- th quarter - winning margin [301]: 333 outcomes
