# NBA MARKET STUDY — every SportyBet NBA market against the results

Each game's last look before tip-off, every outcome settled from ESPN's final and quarter scores. *Landed* = how often it won; *fair* = SportyBet's own chance (its prices, margin removed); *return* = £1 flat on every outcome at SportyBet's price. Landed above fair on a side = SportyBet under-prices it. Written by `backtest/nba_market_study.py`. A study, not a selector.

Games with a look: 67 · graded (ESPN final): 56

## Regular

| Market | outcomes | landed | fair | return | short side (<2.00): n · landed · fair · return | long side (≥2.00): n · landed · fair · return |
|---|---:|---:|---:|---:|---|---|
| Total points (incl. OT) | 162 | 50.0% | 50.0% | +2.0% | 87 · 55.2% · 63.0% · -15.4% | 75 · 44.0% · 34.9% · +22.3% |
| Handicap (incl. OT) | 156 | 50.0% | 50.0% | -7.4% | 81 · 65.4% · 67.7% · -8.5% | 75 · 33.3% · 30.9% · -6.2% |
| Quarter handicap (Q1-Q3) | 90 | 50.0% | 50.0% | -6.9% | 54 · 59.3% · 54.5% · +2.5% | 36 · 36.1% · 43.2% · -21.0% |
| 1st half total | 66 | 50.0% | 50.0% | -2.7% | 36 · 55.6% · 57.9% · -7.7% | 30 · 43.3% · 40.5% · +3.3% |
| 1st half handicap | 62 | 50.0% | 50.0% | -6.1% | 34 · 61.8% · 58.0% · +1.6% | 28 · 35.7% · 40.3% · -15.5% |
| Home team points (incl. OT) | 30 | 50.0% | 50.0% | -3.5% | 18 · 50.0% · 53.4% · -10.3% | 12 · 50.0% · 44.9% · +6.7% |
| Away team points (incl. OT) | 30 | 50.0% | 50.0% | -7.8% | 18 · 66.7% · 53.5% · +18.4% | 12 · 25.0% · 44.8% · -47.1% |
| Half time / full time | 27 | 11.1% | 11.1% | -36.5% | — | 27 · 11.1% · 11.1% · -36.5% |
| 1st quarter total | 22 | 50.0% | 50.0% | -4.9% | 21 · 47.6% · 50.1% · -9.9% | 1 · 100.0% · 47.8% · +100.0% |
| 1X2 (regulation) | 9 | 33.3% | 33.3% | -28.0% | 3 · 33.3% · 51.5% · -35.7% | 6 · 33.3% · 24.3% · -24.2% |
| Winner (incl. OT) | 6 | 50.0% | 50.0% | +6.3% | 3 · 33.3% · 54.8% · -37.3% | 3 · 66.7% · 45.2% · +50.0% |
| Total points (regulation) | 6 | 50.0% | 50.0% | -6.7% | 5 · 60.0% · 50.6% · +12.0% | 1 · 0.0% · 46.9% · -100.0% |

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

## Seen, not settled (rule not confirmed — PENDING)

- Anunoby, OG total -point field goals (incl. overtime) [924]: 2 outcomes
- Anunoby, OG total assists (incl. overtime) [922]: 2 outcomes
- Anunoby, OG total points (incl. overtime) [921]: 2 outcomes
- Anunoby, OG total rebounds (incl. overtime) [923]: 2 outcomes
- Any team to lead by [967]: 18 outcomes
- Any team to win all quarters [1199]: 6 outcomes
- Any team to win both halves [1197]: 6 outcomes
- Any team total maximum consecutive points [964]: 6 outcomes
- Any team winning margin (incl. overtime) [849]: 21 outcomes
- Away Team to Win Both Halves [49]: 6 outcomes
- Bona, Adem total points (incl. overtime) [921]: 2 outcomes
- Bona, Adem total rebounds (incl. overtime) [923]: 2 outcomes
- Boston Celtics to lead by [966]: 6 outcomes
- Boston Celtics to win all quarters [1314]: 2 outcomes
- Boston Celtics total maximum consecutive points [963]: 2 outcomes
- Bridges, Mikal total -point field goals (incl. overtime) [924]: 2 outcomes
- Bridges, Mikal total points (incl. overtime) [921]: 2 outcomes
- Bridges, Mikal total rebounds (incl. overtime) [923]: 2 outcomes
- Brown, Jaylen total -point field goals (incl. overtime) [924]: 2 outcomes
- Brown, Jaylen total assists (incl. overtime) [922]: 2 outcomes
- Brown, Jaylen total points (incl. overtime) [921]: 2 outcomes
- Brown, Jaylen total rebounds (incl. overtime) [923]: 2 outcomes
- Brunson, Jalen total -point field goals (incl. overtime) [924]: 2 outcomes
- Brunson, Jalen total assists (incl. overtime) [922]: 2 outcomes
- Brunson, Jalen total points (incl. overtime) [921]: 2 outcomes
- Brunson, Jalen total rebounds (incl. overtime) [923]: 2 outcomes
- Bryant, Carter total -point field goals (incl. overtime) [924]: 2 outcomes
- Bryant, Carter total points (incl. overtime) [921]: 2 outcomes
- Caldwell-Pope, Kentavious total points (incl. overtime) [921]: 2 outcomes
- Caruso, Alex total -point field goals (incl. overtime) [924]: 2 outcomes
- Caruso, Alex total assists (incl. overtime) [922]: 2 outcomes
- Caruso, Alex total points (incl. overtime) [921]: 2 outcomes
- Caruso, Alex total rebounds (incl. overtime) [923]: 2 outcomes
- Castle, Stephon total -point field goals (incl. overtime) [924]: 2 outcomes
- Castle, Stephon total assists (incl. overtime) [922]: 2 outcomes
- Castle, Stephon total points (incl. overtime) [921]: 2 outcomes
- Castle, Stephon total rebounds (incl. overtime) [923]: 2 outcomes
- Champagnie, Julian total -point field goals (incl. overtime) [924]: 2 outcomes
- Champagnie, Julian total assists (incl. overtime) [922]: 2 outcomes
- Champagnie, Julian total points (incl. overtime) [921]: 2 outcomes
- Champagnie, Julian total rebounds (incl. overtime) [923]: 2 outcomes
- Collins, John total -point field goals (incl. overtime) [924]: 2 outcomes
- Collins, John total assists (incl. overtime) [922]: 2 outcomes
- Collins, John total points (incl. overtime) [921]: 2 outcomes
- Collins, John total rebounds (incl. overtime) [923]: 2 outcomes
- Cunningham, Cade total -point field goals (incl. overtime) [924]: 2 outcomes
- Cunningham, Cade total assists (incl. overtime) [922]: 2 outcomes
- Cunningham, Cade total points (incl. overtime) [921]: 2 outcomes
- Cunningham, Cade total rebounds (incl. overtime) [923]: 2 outcomes
- Detroit Pistons to lead by [965]: 6 outcomes
- Detroit Pistons to win all quarters [1313]: 2 outcomes
- Detroit Pistons total maximum consecutive points [962]: 2 outcomes
- Draw No Bet [11]: 6 outcomes
- Drummond, Andre total points (incl. overtime) [921]: 2 outcomes
- Drummond, Andre total rebounds (incl. overtime) [923]: 2 outcomes
- Duren, Jalen total assists (incl. overtime) [922]: 2 outcomes
- Duren, Jalen total points (incl. overtime) [921]: 2 outcomes
- Duren, Jalen total rebounds (incl. overtime) [923]: 2 outcomes
- Edgecombe, VJ total -point field goals (incl. overtime) [924]: 2 outcomes
- Edgecombe, VJ total assists (incl. overtime) [922]: 2 outcomes
- Edgecombe, VJ total points (incl. overtime) [921]: 2 outcomes
- Edgecombe, VJ total rebounds (incl. overtime) [923]: 2 outcomes
- Embiid, Joel total -point field goals (incl. overtime) [924]: 2 outcomes
- Embiid, Joel total assists (incl. overtime) [922]: 2 outcomes
- Embiid, Joel total points (incl. overtime) [921]: 2 outcomes
- Embiid, Joel total rebounds (incl. overtime) [923]: 2 outcomes
- Fox, De'Aaron total -point field goals (incl. overtime) [924]: 2 outcomes
- Fox, De'Aaron total assists (incl. overtime) [922]: 2 outcomes
- Fox, De'Aaron total points (incl. overtime) [921]: 2 outcomes
- Fox, De'Aaron total rebounds (incl. overtime) [923]: 2 outcomes
- George, Paul total -point field goals (incl. overtime) [924]: 2 outcomes
- George, Paul total assists (incl. overtime) [922]: 2 outcomes
- George, Paul total points (incl. overtime) [921]: 2 outcomes
- George, Paul total rebounds (incl. overtime) [923]: 2 outcomes
- Gilgeous-Alexander, Shai total -point field goals (incl. overtime) [924]: 2 outcomes
- Gilgeous-Alexander, Shai total assists (incl. overtime) [922]: 2 outcomes
- Gilgeous-Alexander, Shai total points (incl. overtime) [921]: 2 outcomes
- Gilgeous-Alexander, Shai total rebounds (incl. overtime) [923]: 2 outcomes
- Handicap (including OT) & Total (including OT) [1174]: 12 outcomes
- Handicap : [14]: 9 outcomes
- Harper, Dylan total -point field goals (incl. overtime) [924]: 2 outcomes
- Harper, Dylan total assists (incl. overtime) [922]: 2 outcomes
- Harper, Dylan total points (incl. overtime) [921]: 2 outcomes
- Harper, Dylan total rebounds (incl. overtime) [923]: 2 outcomes
- Hart, Josh total -point field goals (incl. overtime) [924]: 2 outcomes
- Hart, Josh total assists (incl. overtime) [922]: 2 outcomes
- Hart, Josh total points (incl. overtime) [921]: 2 outcomes
- Hart, Josh total rebounds (incl. overtime) [923]: 2 outcomes
- Hartenstein, Isaiah total assists (incl. overtime) [922]: 2 outcomes
- Hartenstein, Isaiah total points (incl. overtime) [921]: 2 outcomes
- Hartenstein, Isaiah total rebounds (incl. overtime) [923]: 2 outcomes
- Highest Scoring Half [52]: 6 outcomes
- Highest scoring quarter - Over/Under [1193]: 6 outcomes
- Highest scoring quarter [234]: 15 outcomes
- Holmgren, Chet total -point field goals (incl. overtime) [924]: 2 outcomes
- Holmgren, Chet total assists (incl. overtime) [922]: 2 outcomes
- Holmgren, Chet total points (incl. overtime) [921]: 2 outcomes
- Holmgren, Chet total rebounds (incl. overtime) [923]: 2 outcomes
- Home Team to Win Both Halves [48]: 6 outcomes
- James, LeBron total -point field goals (incl. overtime) [924]: 2 outcomes
- James, LeBron total assists (incl. overtime) [922]: 2 outcomes
- James, LeBron total points (incl. overtime) [921]: 2 outcomes
- James, LeBron total rebounds (incl. overtime) [923]: 2 outcomes
- Jenkins, Daniss total -point field goals (incl. overtime) [924]: 2 outcomes
- Jenkins, Daniss total assists (incl. overtime) [922]: 2 outcomes
- Jenkins, Daniss total points (incl. overtime) [921]: 2 outcomes
- Jenkins, Daniss total rebounds (incl. overtime) [923]: 2 outcomes
- Johnson, Keldon total -point field goals (incl. overtime) [924]: 2 outcomes
- Johnson, Keldon total assists (incl. overtime) [922]: 2 outcomes
- Johnson, Keldon total points (incl. overtime) [921]: 2 outcomes
- Johnson, Keldon total rebounds (incl. overtime) [923]: 2 outcomes
- Lowest scoring quarter - Over/Under [1195]: 6 outcomes
- Maxey, Tyrese total -point field goals (incl. overtime) [924]: 2 outcomes
- Maxey, Tyrese total assists (incl. overtime) [922]: 2 outcomes
- Maxey, Tyrese total points (incl. overtime) [921]: 2 outcomes
- Maxey, Tyrese total rebounds (incl. overtime) [923]: 2 outcomes
- McBride, Miles total -point field goals (incl. overtime) [924]: 2 outcomes
- McBride, Miles total points (incl. overtime) [921]: 2 outcomes
- McCain, Jared total -point field goals (incl. overtime) [924]: 2 outcomes
- McCain, Jared total assists (incl. overtime) [922]: 2 outcomes
- McCain, Jared total points (incl. overtime) [921]: 2 outcomes
- McCain, Jared total rebounds (incl. overtime) [923]: 2 outcomes
- Mitchell, Ajay total -point field goals (incl. overtime) [924]: 2 outcomes
- Mitchell, Ajay total assists (incl. overtime) [922]: 2 outcomes
- Mitchell, Ajay total points (incl. overtime) [921]: 2 outcomes
- Mitchell, Ajay total rebounds (incl. overtime) [923]: 2 outcomes
- New York Knicks to lead by [965]: 6 outcomes
- New York Knicks to win all quarters [1313]: 2 outcomes
- New York Knicks total maximum consecutive points [962]: 2 outcomes
- Odd/even (incl. overtime) [229]: 6 outcomes
- Oklahoma City Thunder to lead by [966]: 6 outcomes
- Oklahoma City Thunder to win all quarters [1314]: 2 outcomes
- Oklahoma City Thunder total maximum consecutive points [963]: 2 outcomes
- Philadelphia ers to lead by [966]: 6 outcomes
- Philadelphia ers to win all quarters [1314]: 2 outcomes
- Philadelphia ers total maximum consecutive points [963]: 2 outcomes
- Player -point field goals (incl. overtime) [774]: 191 outcomes
- Player assists (incl. overtime) [770]: 243 outcomes
- Player points (incl. overtime) [768]: 834 outcomes
- Player rebounds (incl. overtime) [772]: 368 outcomes
- Point range [298]: 36 outcomes
- Pritchard, Payton total -point field goals (incl. overtime) [924]: 2 outcomes
- Pritchard, Payton total assists (incl. overtime) [922]: 2 outcomes
- Pritchard, Payton total points (incl. overtime) [921]: 2 outcomes
- Pritchard, Payton total rebounds (incl. overtime) [923]: 2 outcomes
- Quarter handicap (Q1-Q3): 30 outcomes
- Queta, Neemias total points (incl. overtime) [921]: 2 outcomes
- Queta, Neemias total rebounds (incl. overtime) [923]: 2 outcomes
- Race to  points (incl. overtime) [230]: 24 outcomes
- Reed, Paul total assists (incl. overtime) [922]: 2 outcomes
- Reed, Paul total points (incl. overtime) [921]: 2 outcomes
- Reed, Paul total rebounds (incl. overtime) [923]: 2 outcomes
- Robinson, Duncan total -point field goals (incl. overtime) [924]: 2 outcomes
- Robinson, Duncan total assists (incl. overtime) [922]: 2 outcomes
- Robinson, Duncan total points (incl. overtime) [921]: 2 outcomes
- Robinson, Duncan total rebounds (incl. overtime) [923]: 2 outcomes
- Robinson, Mitchell total points (incl. overtime) [921]: 2 outcomes
- Robinson, Mitchell total rebounds (incl. overtime) [923]: 2 outcomes
- San Antonio Spurs to lead by [965]: 6 outcomes
- San Antonio Spurs to win all quarters [1313]: 2 outcomes
- San Antonio Spurs total maximum consecutive points [962]: 2 outcomes
- Shamet, Landry total -point field goals (incl. overtime) [924]: 2 outcomes
- Shamet, Landry total points (incl. overtime) [921]: 2 outcomes
- Shamet, Landry total rebounds (incl. overtime) [923]: 2 outcomes
- Simons, Anfernee total -point field goals (incl. overtime) [924]: 2 outcomes
- Simons, Anfernee total assists (incl. overtime) [922]: 2 outcomes
- Simons, Anfernee total points (incl. overtime) [921]: 2 outcomes
- Simons, Anfernee total rebounds (incl. overtime) [923]: 2 outcomes
- Tatum, Jayson total -point field goals (incl. overtime) [924]: 2 outcomes
- Tatum, Jayson total assists (incl. overtime) [922]: 2 outcomes
- Tatum, Jayson total points (incl. overtime) [921]: 2 outcomes
- Tatum, Jayson total rebounds (incl. overtime) [923]: 2 outcomes
- Team to win all quarters [1203]: 9 outcomes
- Team to win both halves [1201]: 9 outcomes
- Thompson, Ausar total assists (incl. overtime) [922]: 2 outcomes
- Thompson, Ausar total points (incl. overtime) [921]: 2 outcomes
- Thompson, Ausar total rebounds (incl. overtime) [923]: 2 outcomes
- Total (over-exact-under) [297]: 9 outcomes
- Towns, Karl-Anthony total -point field goals (incl. overtime) [924]: 2 outcomes
- Towns, Karl-Anthony total assists (incl. overtime) [922]: 2 outcomes
- Towns, Karl-Anthony total points (incl. overtime) [921]: 2 outcomes
- Towns, Karl-Anthony total rebounds (incl. overtime) [923]: 2 outcomes
- Vassell, Devin total -point field goals (incl. overtime) [924]: 2 outcomes
- Vassell, Devin total assists (incl. overtime) [922]: 2 outcomes
- Vassell, Devin total points (incl. overtime) [921]: 2 outcomes
- Vassell, Devin total rebounds (incl. overtime) [923]: 2 outcomes
- Wallace, Cason total -point field goals (incl. overtime) [924]: 2 outcomes
- Wallace, Cason total assists (incl. overtime) [922]: 2 outcomes
- Wallace, Cason total points (incl. overtime) [921]: 2 outcomes
- Wallace, Cason total rebounds (incl. overtime) [923]: 2 outcomes
- Walsh, Jordan total points (incl. overtime) [921]: 2 outcomes
- Walsh, Jordan total rebounds (incl. overtime) [923]: 2 outcomes
- Wembanyama, Victor total -point field goals (incl. overtime) [924]: 2 outcomes
- Wembanyama, Victor total assists (incl. overtime) [922]: 2 outcomes
- Wembanyama, Victor total points (incl. overtime) [921]: 2 outcomes
- Wembanyama, Victor total rebounds (incl. overtime) [923]: 2 outcomes
- White, Derrick total -point field goals (incl. overtime) [924]: 2 outcomes
- White, Derrick total assists (incl. overtime) [922]: 2 outcomes
- White, Derrick total points (incl. overtime) [921]: 2 outcomes
- White, Derrick total rebounds (incl. overtime) [923]: 2 outcomes
- Will There be Overtime [220]: 6 outcomes
- Williams, Jalen total -point field goals (incl. overtime) [924]: 2 outcomes
- Williams, Jalen total assists (incl. overtime) [922]: 2 outcomes
- Williams, Jalen total points (incl. overtime) [921]: 2 outcomes
- Williams, Jalen total rebounds (incl. overtime) [923]: 2 outcomes
- Winner & Over/Under (incl. overtime) [292]: 12 outcomes
- Winning margin (incl. overtime) [290]: 63 outcomes
- X & Over/Under [37]: 18 outcomes
- nd Half - Asian Handicap [88]: 66 outcomes
- nd Half - Draw No Bet [86]: 6 outcomes
- nd Half - Odd/Even [94]: 6 outcomes
- nd Half - Over/Under [90]: 66 outcomes
- nd Half - X [83]: 9 outcomes
- nd quarter - draw no bet [302]: 6 outcomes
- nd quarter - last point [960]: 6 outcomes
- nd quarter - odd/even [304]: 6 outcomes
- nd quarter - winning margin [301]: 9 outcomes
- nd quarter - x [235]: 9 outcomes
- rd quarter - draw no bet [302]: 6 outcomes
- rd quarter - odd/even [304]: 6 outcomes
- rd quarter - winning margin [301]: 9 outcomes
- rd quarter - x [235]: 9 outcomes
- st Half - Draw No Bet [64]: 6 outcomes
- st Half - Odd/Even [74]: 6 outcomes
- st Half - X [60]: 9 outcomes
- st free throw scored [961]: 6 outcomes
- st half - Boston Celtics Over/Under [70]: 10 outcomes
- st half - Detroit Pistons Over/Under [69]: 10 outcomes
- st half - New York Knicks Over/Under [69]: 10 outcomes
- st half - Oklahoma City Thunder Over/Under [70]: 10 outcomes
- st half - Philadelphia ers Over/Under [70]: 10 outcomes
- st half - San Antonio Spurs Over/Under [69]: 10 outcomes
- st half handicap & st half total [1178]: 12 outcomes
- st half x & st half total [1177]: 18 outcomes
- st quarter - Boston Celtics Over/Under [757]: 10 outcomes
- st quarter - Detroit Pistons Over/Under [756]: 10 outcomes
- st quarter - New York Knicks Over/Under [756]: 10 outcomes
- st quarter - Oklahoma City Thunder Over/Under [757]: 10 outcomes
- st quarter - Philadelphia ers Over/Under [757]: 10 outcomes
- st quarter - San Antonio Spurs Over/Under [756]: 10 outcomes
- st quarter - draw no bet [302]: 6 outcomes
- st quarter - last point [960]: 6 outcomes
- st quarter - odd/even [304]: 6 outcomes
- st quarter - winning margin [301]: 9 outcomes
- st quarter - x [235]: 9 outcomes
- st quarter handicap & st quarter total [1176]: 12 outcomes
- st quarter x & st quarter total [1175]: 18 outcomes
- th quarter - draw no bet [302]: 6 outcomes
- th quarter - odd/even [304]: 6 outcomes
- th quarter - winning margin [301]: 9 outcomes
- th quarter - x [235]: 9 outcomes
