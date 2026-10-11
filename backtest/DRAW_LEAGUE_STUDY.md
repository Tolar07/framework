# DRAW LEAGUE STUDY — which draws are worth backing?

Written by `backtest/draw_league_study.py`: 148,922 matches, 40 leagues, seasons 2012–2027 (football-data.co.uk). Bet at bet365's draw price; market = Pinnacle close, margin removed. ± is one standard error.

## A · Every draw, by league (300+ matches)

| League | matches | real draws | market said | real − market | £1 return ± se |
|---|---|---|---|---|---|
| Serie B | 4422 | 32.1% | 29.7% | +2.4 pts | +3.2% ± 2.3% |
| Scottish Champ | 1933 | 27.9% | 26.0% | +1.9 pts | +0.1% ± 3.7% |
| Bundesliga | 3402 | 24.6% | 23.8% | +0.9 pts | -1.1% ± 3.1% |
| Eredivisie | 3354 | 23.7% | 22.4% | +1.2 pts | -2.0% ± 3.2% |
| Argentina Copa De La Liga Profesional | 920 | 30.7% | 29.5% | +1.2 pts | -2.3% ± 4.9% |
| 2. Bundesliga | 3417 | 27.1% | 26.4% | +0.6 pts | -3.4% ± 2.7% |
| Greek Super League | 2624 | 27.2% | 26.1% | +1.1 pts | -3.7% ± 3.2% |
| La Liga 2 | 5132 | 30.1% | 29.9% | +0.2 pts | -3.7% ± 2.1% |
| China Super League | 3010 | 25.4% | 23.9% | +1.5 pts | -3.8% ± 3.1% |
| Austria Bundesliga | 2680 | 24.9% | 24.3% | +0.7 pts | -3.8% ± 3.4% |
| La Liga | 4249 | 26.0% | 25.8% | +0.2 pts | -4.8% ± 2.6% |
| Serie A | 4227 | 25.4% | 25.3% | +0.1 pts | -4.9% ± 2.6% |
| Switzerland Super League | 2726 | 25.5% | 24.9% | +0.6 pts | -4.9% ± 3.2% |
| Denmark Superliga | 3006 | 26.1% | 25.7% | +0.4 pts | -5.4% ± 2.9% |
| Argentina Liga Profesional | 5479 | 30.2% | 29.8% | +0.4 pts | -5.4% ± 2.0% |
| Premier League | 4230 | 23.8% | 24.2% | -0.4 pts | -5.7% ± 2.7% |
| League Two | 6056 | 26.9% | 27.3% | -0.5 pts | -5.7% ± 2.0% |
| Championship | 6167 | 26.7% | 27.3% | -0.6 pts | -5.9% ± 2.0% |
| Mexico Liga MX | 4743 | 27.1% | 26.8% | +0.3 pts | -6.5% ± 2.3% |
| USA MLS | 6221 | 25.2% | 25.2% | +0.0 pts | -6.6% ± 2.1% |
| Ligue 1 | 3899 | 25.5% | 25.9% | -0.3 pts | -7.0% ± 2.6% |
| Poland Ekstraklasa | 4160 | 27.1% | 27.2% | -0.1 pts | -7.6% ± 2.4% |
| League One | 6008 | 25.8% | 26.8% | -1.0 pts | -7.6% ± 2.0% |
| Romania Superliga | 4262 | 27.8% | 27.7% | +0.1 pts | -7.7% ± 2.3% |
| Super Lig | 3711 | 25.5% | 25.5% | -0.0 pts | -7.8% ± 2.6% |
| Belgian Pro League | 3102 | 24.6% | 24.6% | -0.0 pts | -8.0% ± 2.9% |
| Scottish Prem | 2499 | 23.9% | 24.4% | -0.5 pts | -8.0% ± 3.5% |
| Sweden Allsvenskan | 3560 | 24.9% | 25.1% | -0.1 pts | -8.2% ± 2.7% |
| Ligue 2 | 3983 | 28.8% | 29.4% | -0.6 pts | -8.4% ± 2.3% |
| Brazil Serie A | 5608 | 26.9% | 27.3% | -0.4 pts | -8.5% ± 2.0% |
| Norway Eliteserien | 3550 | 24.0% | 24.4% | -0.4 pts | -9.3% ± 2.8% |
| Finland Veikkausliiga | 2697 | 25.5% | 26.0% | -0.5 pts | -9.6% ± 3.0% |
| National League | 5977 | 25.2% | 25.7% | -0.5 pts | -9.8% ± 2.0% |
| Russia Premier League | 3334 | 25.7% | 26.5% | -0.8 pts | -10.4% ± 2.7% |
| Ireland Premier Division | 2724 | 24.8% | 25.3% | -0.5 pts | -10.6% ± 3.1% |
| Scottish L1 | 1908 | 23.4% | 24.8% | -1.5 pts | -12.6% ± 3.7% |
| Primeira Liga | 3426 | 24.3% | 25.2% | -0.9 pts | -12.9% ± 2.7% |
| Scottish L2 | 1911 | 23.7% | 25.3% | -1.7 pts | -13.8% ± 3.6% |
| Japan J1 League | 4603 | 24.8% | 26.6% | -1.8 pts | -14.3% ± 2.2% |
| **ALL** | 148922 | 26.3% | 26.3% | -0.0 pts | -6.7% ± 0.4% |

The market prices draws almost exactly; backing every draw loses the margin.

## B · Walk-forward: can the LEAGUE pick the draws?

Each season, back every draw in the leagues whose draws made money (and landed 1+ pt above the market) over the 4 seasons before.

| test season | leagues picked | bets | draws | £1 return |
|---|---|---|---|---|
| 2019 | Scottish Champ, Serie B | 522 | 30.8% | +0.9% |
| 2020 | Scottish Champ, Serie B | 510 | 26.3% | -12.1% |
| 2021 | 2. Bundesliga, Serie B | 677 | 29.7% | -1.6% |
| 2022 | Bundesliga, La Liga, Norway Eliteserien, Serie B | 1307 | 27.4% | -1.0% |
| 2023 | 2. Bundesliga, Austria Bundesliga, La Liga, Scottish Champ, Serie B, Switzerland Super League | 1623 | 27.4% | -2.6% |
| 2024 | Austria Bundesliga, Scottish Champ, Serie B, Switzerland Super League | 983 | 28.9% | +1.7% |
| 2025 | Argentina Copa De La Liga Profesional, Austria Bundesliga, Bundesliga, Eredivisie, Scottish Champ, Serie A, Serie B, Switzerland Super League | 1972 | 27.6% | +1.5% |
| 2026 | Argentina Copa De La Liga Profesional, Austria Bundesliga, Bundesliga, Denmark Superliga, Eredivisie, Serie A, Serie B, Switzerland Super League | 1984 | 26.4% | -2.9% |
| 2027 | Argentina Copa De La Liga Profesional, Austria Bundesliga, Bundesliga, China Super League, Eredivisie, Ireland Premier Division, Serie A, Serie B, Switzerland Super League | 295 | 22.0% | -10.3% |
| **all** | | 9873 | 27.5% | **-1.7% ± 1.6%** |

No: a league's draw history does not carry into the next season.

## C · Which GAMES draw? (filter fixed on seasons to 2021, tested on 2022 on)

| filter | to-2021 bets | to-2021 return | 2022-on bets | draws | 2022-on return ± se |
|---|---|---|---|---|---|
| every game | 85859 | -7.4% | 63063 | 26.3% | -5.6% ± 0.6% |
| draw price ≤ 3.20 | 18763 | -2.8% | 12296 | 32.1% | -2.0% ± 1.3% |
| evenly matched (win chances within 10 pts) | 20253 | -4.3% | 14519 | 30.0% | -2.3% ± 1.2% |
| priced low-scoring (Under 2.5 ≤ 1.75) | 17542 | -1.2% | 12642 | 30.4% | -1.7% ± 1.3% |
| market draw chance ≥ 32% | 4135 | +2.0% | 3901 | 34.1% | +1.0% ± 2.3% |
| market draw chance < 22% | 11879 | -15.0% | 9556 | 17.0% | -14.6% ± 2.0% |
| evenly matched + Under 2.5 ≤ 1.75 | 5703 | +2.2% | 4062 | 32.6% | +2.3% ± 2.3% |
| **evenly matched + Under 2.5 ≤ 1.70 (TABLE 3E)** | 4531 | +3.5% | 3235 | 33.5% | +4.3% ± 2.6% |
| evenly matched + Under 2.5 ≤ 1.65 | 3385 | +4.8% | 2326 | 33.8% | +4.2% ± 3.0% |

## D · The TABLE 3E rule

| season | games | draws | £1 return |
|---|---|---|---|
| 2016 | 846 | 33.5% | +4.8% |
| 2017 | 777 | 34.9% | +8.1% |
| 2018 | 666 | 30.0% | -6.4% |
| 2019 | 723 | 33.2% | +3.4% |
| 2020 | 628 | 34.7% | +7.4% |
| 2021 | 891 | 33.6% | +3.2% |
| 2022 | 708 | 35.5% | +11.2% |
| 2023 | 760 | 35.0% | +9.3% |
| 2024 | 490 | 32.4% | +1.1% |
| 2025 | 575 | 30.6% | -4.6% |
| 2026 | 639 | 31.9% | -1.6% |

| league (150+ games) | games | draws | £1 return |
|---|---|---|---|
| La Liga 2 | 1111 | 34% | +2.9% |
| Ligue 2 | 882 | 35% | +5.6% |
| Serie B | 829 | 38% | +14.1% |
| Championship | 750 | 30% | -3.4% |
| League Two | 617 | 30% | -2.0% |
| Primeira Liga | 497 | 29% | -10.3% |
| La Liga | 454 | 35% | +9.0% |
| League One | 436 | 28% | -8.6% |
| Ligue 1 | 382 | 36% | +12.8% |
| Greek Super League | 355 | 37% | +13.5% |
| Serie A | 261 | 33% | +2.0% |
| National League | 248 | 38% | +24.8% |
| Premier League | 205 | 26% | -17.4% |
| Scottish Prem | 202 | 31% | -1.0% |

**2-leg draw doubles** (2022 on, same-day games paired): 1344 doubles, 148 landed (11.0%, about 1 in 9), £1 return +5.8%.

## Verdict

- The league is not the edge; the type of game is. Evenly matched sides in a game priced low-scoring draw about 1 in 3, and beat bet365's price in both periods.
- The edge is thin (one to two standard errors) and the latest seasons were negative. So TABLE 3E is a minimal-stake test, graded as its own line (`draws` in the picks ledger) and as paper rule F14 / paper acca A5 on every game worldwide.
- A draw double lands about 1 time in 9. Expect long losing runs; judge it on 100+ bets.
- SportyBet's 1X2 margin averaged 4.3% on our covered leagues but 8.7% across all its football (10-11 Oct 2026 sweep). The table skips any 1X2 book above 9%.
- History uses the bookmaker-average Under 2.5 price; live uses SportyBet's own, which carries more margin (shorter), so a few more games qualify live than in the study.
