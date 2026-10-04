# DRAW STUDY — do team profiles predict draws beyond the market?

Matches with a profile for both teams and Pinnacle + bet365 prices: 9280 (learn 7145, test 2135)

## Q1 · Real draw rate vs the market, by profile signal (all seasons)
| profile tendency − market (close) | n | market says | real draws |
|---|---|---|---|
| -1.00 to -0.05 | 2447 | 27.5% | 28.7% |
| -0.05 to +0.00 | 2016 | 26.3% | 27.0% |
| +0.00 to +0.05 | 2104 | 25.1% | 27.2% |
| +0.05 to +0.10 | 1500 | 23.7% | 22.5% |
| +0.10 to +1.00 | 1213 | 21.1% | 21.4% |

## Q2 · Pinnacle closing: add the profile signal?
- best weight learned on 23/24+24/25: k = 0.00
- test 25/26 Brier (draw / no draw): market alone 0.19053 · market + profile 0.19053 (no better)

## Q3 · bet365 opening: add the profile signal?
- best weight learned on 23/24+24/25: k = 0.00
- test 25/26 Brier (draw / no draw): market alone 0.19054 · market + profile 0.19054 (no better)

## Q4 · By league: are draws under-priced (real − market, Pinnacle close)?
| League | learn n | learn real−market | test n | test real−market |
|---|---|---|---|---|
| Belgian Pro League | 561 | +2.9 pts | 84 | +5.5 pts |
| Bundesliga | 546 | +3.3 pts | 143 | -2.2 pts |
| Championship | 1000 | -0.2 pts | 259 | -0.9 pts |
| Eredivisie | 540 | +3.2 pts | 136 | +3.1 pts |
| La Liga | 683 | +1.2 pts | 172 | -0.8 pts |
| League One | 477 | -1.9 pts | 131 | -4.0 pts |
| League Two | 478 | +2.8 pts | 133 | -4.7 pts |
| Ligue 1 | 540 | -2.8 pts | 147 | -2.9 pts |
| Premier League | 682 | +0.0 pts | 198 | +0.8 pts |
| Primeira Liga | 542 | +1.4 pts | 142 | +2.6 pts |
| Serie A | 682 | +2.6 pts | 186 | +1.5 pts |

All leagues: real draws +0.8 pts vs the closing price. Leagues under-pricing draws by 2+ pts in BOTH periods: Belgian Pro League, Eredivisie.

