# NBA MARKET STUDY — every SportyBet NBA market against the results

Each game's last look before tip-off, every outcome settled from ESPN's final and quarter scores. *Landed* = how often it won; *fair* = SportyBet's own chance (its prices, margin removed); *return* = £1 flat on every outcome at SportyBet's price. Landed above fair on a side = SportyBet under-prices it. Written by `backtest/nba_market_study.py`. A study, not a selector.

Games with a look: 56 · graded (ESPN final): 54

## Regular

| Market | outcomes | landed | fair | return | short side (<2.00): n · landed · fair · return | long side (≥2.00): n · landed · fair · return |
|---|---:|---:|---:|---:|---|---|
| Total points (incl. OT) | 54 | 50.0% | 50.0% | +1.4% | 29 · 55.2% · 62.9% · -15.4% | 25 · 44.0% · 35.0% · +20.8% |
| Handicap (incl. OT) | 52 | 50.0% | 50.0% | -13.6% | 27 · 70.4% · 67.5% · -1.9% | 25 · 28.0% · 31.0% · -26.2% |
| Quarter handicap (Q1-Q3) | 30 | 50.0% | 50.0% | -8.0% | 18 · 61.1% · 54.5% · +5.3% | 12 · 33.3% · 43.3% · -27.9% |
| 1st half total | 22 | 50.0% | 50.0% | +1.9% | 12 · 50.0% · 58.0% · -15.3% | 10 · 50.0% · 40.4% · +22.5% |
| 1st half handicap | 18 | 50.0% | 50.0% | -1.8% | 10 · 50.0% · 56.8% · -15.8% | 8 · 50.0% · 41.5% · +15.6% |
| Home team points (incl. OT) | 10 | 50.0% | 50.0% | -3.9% | 6 · 50.0% · 53.5% · -10.7% | 4 · 50.0% · 44.8% · +6.2% |
| Away team points (incl. OT) | 10 | 50.0% | 50.0% | -7.7% | 6 · 66.7% · 53.5% · +18.8% | 4 · 25.0% · 44.7% · -47.5% |
| Half time / full time | 9 | 11.1% | 11.1% | -24.4% | — | 9 · 11.1% · 11.1% · -24.4% |
| 1st quarter total | 6 | 50.0% | 50.0% | -7.8% | 6 · 50.0% · 50.0% · -7.8% | — |
| 1X2 (regulation) | 3 | 33.3% | 33.3% | -31.7% | 1 · 0.0% · 48.5% · -100.0% | 2 · 50.0% · 25.7% · +2.5% |
| Winner (incl. OT) | 2 | 50.0% | 50.0% | +0.5% | 1 · 0.0% · 51.7% · -100.0% | 1 · 100.0% · 48.3% · +101.0% |
| Total points (regulation) | 2 | 50.0% | 50.0% | -4.0% | 2 · 50.0% · 50.0% · -4.0% | — |

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

- Any team to lead by [967]: 6 outcomes
- Any team to win all quarters [1199]: 2 outcomes
- Any team to win both halves [1197]: 2 outcomes
- Any team total maximum consecutive points [964]: 2 outcomes
- Any team winning margin (incl. overtime) [849]: 7 outcomes
- Away Team to Win Both Halves [49]: 2 outcomes
- Boston Celtics to lead by [966]: 6 outcomes
- Boston Celtics to win all quarters [1314]: 2 outcomes
- Boston Celtics total maximum consecutive points [963]: 2 outcomes
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
- Draw No Bet [11]: 2 outcomes
- Duren, Jalen total assists (incl. overtime) [922]: 2 outcomes
- Duren, Jalen total points (incl. overtime) [921]: 2 outcomes
- Duren, Jalen total rebounds (incl. overtime) [923]: 2 outcomes
- George, Paul total -point field goals (incl. overtime) [924]: 2 outcomes
- George, Paul total assists (incl. overtime) [922]: 2 outcomes
- George, Paul total points (incl. overtime) [921]: 2 outcomes
- George, Paul total rebounds (incl. overtime) [923]: 2 outcomes
- Handicap (including OT) & Total (including OT) [1174]: 4 outcomes
- Handicap : [14]: 3 outcomes
- Highest scoring quarter - Over/Under [1193]: 2 outcomes
- Highest scoring quarter [234]: 5 outcomes
- Home Team to Win Both Halves [48]: 2 outcomes
- Jenkins, Daniss total -point field goals (incl. overtime) [924]: 2 outcomes
- Jenkins, Daniss total assists (incl. overtime) [922]: 2 outcomes
- Jenkins, Daniss total points (incl. overtime) [921]: 2 outcomes
- Jenkins, Daniss total rebounds (incl. overtime) [923]: 2 outcomes
- Lowest scoring quarter - Over/Under [1195]: 2 outcomes
- Odd/even (incl. overtime) [229]: 2 outcomes
- Player -point field goals (incl. overtime) [774]: 47 outcomes
- Player assists (incl. overtime) [770]: 72 outcomes
- Player points (incl. overtime) [768]: 256 outcomes
- Player rebounds (incl. overtime) [772]: 122 outcomes
- Point range [298]: 12 outcomes
- Pritchard, Payton total -point field goals (incl. overtime) [924]: 2 outcomes
- Pritchard, Payton total assists (incl. overtime) [922]: 2 outcomes
- Pritchard, Payton total points (incl. overtime) [921]: 2 outcomes
- Pritchard, Payton total rebounds (incl. overtime) [923]: 2 outcomes
- Quarter handicap (Q1-Q3): 10 outcomes
- Queta, Neemias total points (incl. overtime) [921]: 2 outcomes
- Queta, Neemias total rebounds (incl. overtime) [923]: 2 outcomes
- Race to  points (incl. overtime) [230]: 8 outcomes
- Reed, Paul total assists (incl. overtime) [922]: 2 outcomes
- Reed, Paul total points (incl. overtime) [921]: 2 outcomes
- Reed, Paul total rebounds (incl. overtime) [923]: 2 outcomes
- Robinson, Duncan total -point field goals (incl. overtime) [924]: 2 outcomes
- Robinson, Duncan total assists (incl. overtime) [922]: 2 outcomes
- Robinson, Duncan total points (incl. overtime) [921]: 2 outcomes
- Robinson, Duncan total rebounds (incl. overtime) [923]: 2 outcomes
- Robinson, Mitchell total points (incl. overtime) [921]: 2 outcomes
- Robinson, Mitchell total rebounds (incl. overtime) [923]: 2 outcomes
- Tatum, Jayson total -point field goals (incl. overtime) [924]: 2 outcomes
- Tatum, Jayson total assists (incl. overtime) [922]: 2 outcomes
- Tatum, Jayson total points (incl. overtime) [921]: 2 outcomes
- Tatum, Jayson total rebounds (incl. overtime) [923]: 2 outcomes
- Team to win all quarters [1203]: 3 outcomes
- Team to win both halves [1201]: 3 outcomes
- Thompson, Ausar total assists (incl. overtime) [922]: 2 outcomes
- Thompson, Ausar total points (incl. overtime) [921]: 2 outcomes
- Thompson, Ausar total rebounds (incl. overtime) [923]: 2 outcomes
- Total (over-exact-under) [297]: 3 outcomes
- Walsh, Jordan total points (incl. overtime) [921]: 2 outcomes
- Walsh, Jordan total rebounds (incl. overtime) [923]: 2 outcomes
- White, Derrick total -point field goals (incl. overtime) [924]: 2 outcomes
- White, Derrick total assists (incl. overtime) [922]: 2 outcomes
- White, Derrick total points (incl. overtime) [921]: 2 outcomes
- White, Derrick total rebounds (incl. overtime) [923]: 2 outcomes
- Will There be Overtime [220]: 2 outcomes
- Winner & Over/Under (incl. overtime) [292]: 4 outcomes
- Winning margin (incl. overtime) [290]: 21 outcomes
- X & Over/Under [37]: 6 outcomes
- nd Half - Asian Handicap [88]: 22 outcomes
- nd Half - Draw No Bet [86]: 2 outcomes
- nd Half - Odd/Even [94]: 2 outcomes
- nd Half - Over/Under [90]: 22 outcomes
- nd Half - X [83]: 3 outcomes
- nd quarter - draw no bet [302]: 2 outcomes
- nd quarter - last point [960]: 2 outcomes
- nd quarter - odd/even [304]: 2 outcomes
- nd quarter - winning margin [301]: 3 outcomes
- nd quarter - x [235]: 3 outcomes
- rd quarter - draw no bet [302]: 2 outcomes
- rd quarter - odd/even [304]: 2 outcomes
- rd quarter - winning margin [301]: 3 outcomes
- rd quarter - x [235]: 3 outcomes
- st Half - Draw No Bet [64]: 2 outcomes
- st Half - Odd/Even [74]: 2 outcomes
- st Half - X [60]: 3 outcomes
- st free throw scored [961]: 2 outcomes
- st half - Boston Celtics Over/Under [70]: 10 outcomes
- st half - Detroit Pistons Over/Under [69]: 10 outcomes
- st half handicap & st half total [1178]: 4 outcomes
- st half x & st half total [1177]: 6 outcomes
- st quarter - Boston Celtics Over/Under [757]: 10 outcomes
- st quarter - Detroit Pistons Over/Under [756]: 10 outcomes
- st quarter - draw no bet [302]: 2 outcomes
- st quarter - last point [960]: 2 outcomes
- st quarter - odd/even [304]: 2 outcomes
- st quarter - winning margin [301]: 3 outcomes
- st quarter - x [235]: 3 outcomes
- st quarter handicap & st quarter total [1176]: 4 outcomes
- st quarter x & st quarter total [1175]: 6 outcomes
- th quarter - draw no bet [302]: 2 outcomes
- th quarter - odd/even [304]: 2 outcomes
- th quarter - winning margin [301]: 3 outcomes
- th quarter - x [235]: 3 outcomes
