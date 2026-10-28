# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

816 matches, 2026-10-04 to 2026-10-27.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| League One | 53 | 2.70 | 2.92 | 28.3 | 8.7 | 4.8 | 12.1 | 3.5 | 0.31 |
| League Two | 49 | 2.80 | 2.76 | 25.7 | 8.0 | 3.7 | 9.9 | 3.9 | 0.35 |
| Championship | 45 | 2.76 | 3.00 | 28.6 | 8.4 | 4.9 | 10.7 | 1.0 | 0.33 |
| FA Cup | 42 | 3.14 | — | — | — | — | — | — | — |
| Serie B | 37 | 2.70 | 2.80 | 28.5 | 8.6 | 4.1 | 9.5 | 3.9 | 0.31 |
| La Liga 2 | 35 | 2.71 | 2.70 | 26.2 | 8.9 | 4.0 | 10.8 | 5.6 | 0.31 |
| Europa League | 34 | 3.26 | 3.13 | 27.6 | 9.9 | 5.1 | 9.3 | 4.1 | 0.33 |
| Serie A | 33 | 3.45 | 3.36 | 29.5 | 10.5 | 5.8 | 9.6 | 3.1 | 0.33 |
| National League | 31 | 3.52 | — | — | — | — | — | — | — |
| Conference League | 31 | 2.84 | 3.03 | 29.1 | 9.4 | 4.8 | 9.8 | 3.8 | 0.30 |
| Premier League | 30 | 2.70 | 2.68 | 26.4 | 8.2 | 4.7 | 9.5 | 4.2 | 0.33 |
| La Liga | 27 | 2.96 | 2.83 | 28.7 | 9.8 | 4.0 | 10.0 | 5.2 | 0.30 |
| Champions League | 27 | 4.52 | 3.73 | 29.5 | 11.7 | 6.7 | 9.9 | 3.2 | 0.39 |
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| Ligue 2 | 26 | 2.85 | 2.53 | 24.8 | 8.7 | 3.7 | 10.1 | 3.9 | 0.33 |
| 2. Bundesliga | 25 | 2.44 | 2.79 | 29.7 | 9.8 | 4.0 | 11.4 | 3.8 | 0.25 |
| Allsvenskan | 25 | 2.84 | 2.71 | 28.5 | 9.4 | 2.8 | 11.2 | 1.2 | 0.30 |
| Eredivisie | 24 | 3.96 | 3.36 | 30.9 | 10.8 | 6.2 | 9.9 | 3.2 | 0.37 |
| Ligue 1 | 24 | 3.17 | 3.01 | 24.5 | 8.6 | 4.2 | 8.6 | 4.3 | 0.37 |
| Ekstraklasa | 22 | 3.23 | 3.05 | 29.5 | 9.5 | 5.0 | 10.4 | 3.7 | 0.34 |
| Turkish Super Lig | 22 | 2.77 | 3.04 | 27.7 | 10.1 | 4.8 | 9.8 | 3.9 | 0.27 |
| Bundesliga | 21 | 3.24 | 3.57 | 30.6 | 10.3 | 5.9 | 10.2 | 3.1 | 0.31 |
| Primeira Liga | 18 | 2.67 | 2.51 | 26.8 | 8.2 | 4.1 | 9.6 | 4.9 | 0.33 |
| Belgian Pro League | 15 | 4.27 | 3.28 | 27.5 | 10.3 | 5.7 | 10.3 | 3.7 | 0.41 |
| Eliteserien | 15 | 3.73 | 3.49 | 32.3 | 10.3 | 4.1 | 11.1 | 3.7 | 0.36 |
| Scottish Premiership | 15 | 3.13 | 3.18 | 30.0 | 10.9 | 4.9 | 10.7 | 3.1 | 0.29 |
| Austrian Bundesliga | 15 | 3.33 | 3.38 | 30.6 | 10.2 | 5.9 | 10.7 | 2.9 | 0.33 |
| HNL | 14 | 2.50 | — | 26.2 | 8.4 | 3.4 | 10.1 | 3.6 | 0.30 |
| Greek Super League | 14 | 3.50 | 2.65 | 24.6 | 8.7 | 4.3 | 8.1 | 4.4 | 0.40 |
| Swiss Super League | 12 | 2.75 | 3.02 | 30.9 | 9.6 | 4.3 | 10.7 | 4.6 | 0.29 |
| Danish Superliga | 9 | 3.78 | 3.43 | 28.9 | 11.3 | 5.1 | 8.6 | 4.6 | 0.33 |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 723 | 59% | 22% | 19% |
| shots on target | 661 | 60% | 21% | 18% |
| big chances | 618 | 62% | 21% | 17% |
| possession | 711 | 39% | 22% | 39% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| Panathinaikos | Conference League | 4 | 3.13 | 0.66 | 6.2–1.8 | 63% | -0.13 |
| Bournemouth | Premier League | 5 | 2.75 | 0.56 | 5.6–2.4 | 56% | -0.35 |
| Bayern Munich | Bundesliga | 5 | 3.40 | 1.33 | 9.8–4.6 | 60% | -0.20 |
| Middlesbrough | Championship | 4 | 2.58 | 0.77 | 9.8–2.5 | 59% | +0.17 |
| Inter | Serie A | 4 | 3.27 | 1.50 | 9.2–4.0 | 60% | -0.52 |
| Bodoe/Glimt | Champions League | 3 | 2.58 | 0.84 | 5.7–5.0 | 61% | -0.25 |
| SC Pisa | Serie B | 3 | 2.21 | 0.53 | 6.0–2.0 | 55% | +0.12 |
| Benfica | Primeira Liga | 4 | 2.69 | 1.04 | 6.2–4.5 | 60% | +0.31 |
| Gornik Zabrze | Ekstraklasa | 3 | 2.38 | 0.74 | 6.7–3.7 | 48% | -0.71 |
| SK Brann | Conference League | 3 | 2.75 | 1.15 | 8.0–3.0 | 73% | -0.75 |
| Mansfield | League One | 4 | 2.38 | 0.80 | 5.2–3.0 | 50% | +0.12 |
| Benevento Calcio | Serie B | 4 | 2.16 | 0.61 | 6.0–2.0 | 51% | -0.16 |
| Huddersfield | League One | 4 | 2.59 | 1.06 | 6.0–3.2 | 41% | -0.09 |
| Stockport County FC | League One | 5 | 2.33 | 0.84 | 4.6–3.8 | 67% | -0.93 |
| Rangers | Scottish Premiership | 3 | 2.60 | 1.17 | 7.3–4.3 | 60% | +0.40 |
| Barcelona | La Liga | 4 | 2.27 | 0.93 | 8.8–3.5 | 71% | +0.98 |
| Club Brugge | Belgian Pro League | 4 | 3.61 | 2.32 | 6.2–6.2 | 55% | -0.11 |
| Milan | Serie A | 3 | 2.45 | 1.16 | 6.3–4.3 | 58% | -0.45 |
| Amed Sportif Faaliyetler | Turkish Super Lig | 3 | 1.81 | 0.61 | 5.0–2.7 | 52% | -0.15 |
| Man City | Premier League | 4 | 2.28 | 1.09 | 6.0–3.5 | 66% | +0.72 |
| Hertha | 2. Bundesliga | 3 | 1.78 | 0.63 | 7.0–3.0 | 57% | -0.78 |
| Palermo | Serie B | 3 | 2.87 | 1.72 | 8.0–3.3 | 48% | -0.21 |
| IF Elfsborg | Allsvenskan | 4 | 1.79 | 0.68 | 5.0–3.2 | 49% | +0.21 |
| GNK Dinamo Zagreb | HNL | 4 | 2.35 | 1.23 | 6.0–3.8 | 50% | -0.85 |
| BK Hacken | Allsvenskan | 3 | 2.00 | 0.89 | 8.3–4.7 | 53% | +0.67 |
| Leicester | League One | 5 | 2.08 | 0.99 | 6.0–4.2 | 64% | +0.12 |
| Brest | Ligue 1 | 3 | 2.36 | 1.33 | 6.0–3.3 | 46% | -0.03 |
| Heidenheim | 2. Bundesliga | 3 | 2.15 | 1.14 | 7.0–5.3 | 50% | -1.48 |
| West Ham | Championship | 3 | 1.96 | 0.98 | 9.0–2.3 | 57% | +1.04 |
| Nancy | Ligue 2 | 3 | 1.64 | 0.68 | 4.7–2.7 | 53% | -0.30 |
| Real Madrid | La Liga | 5 | 2.03 | 1.09 | 7.2–5.6 | 52% | +0.97 |
| Sparta Rotterdam | Eredivisie | 3 | 2.20 | 1.28 | 7.0–4.7 | 42% | +0.14 |
| Lazio | Serie A | 4 | 1.93 | 1.04 | 5.8–3.2 | 58% | +1.57 |
| Eldense | La Liga 2 | 3 | 2.15 | 1.28 | 3.3–5.0 | 52% | -0.49 |
| Nott'm Forest | Premier League | 3 | 2.18 | 1.34 | 4.3–3.7 | 45% | -1.51 |
| Aston Villa | Premier League | 5 | 2.05 | 1.22 | 6.6–3.8 | 47% | +0.75 |
| Goztepe Izmir | Turkish Super Lig | 3 | 1.99 | 1.17 | 5.7–4.3 | 40% | +0.67 |
| Sarpsborg 08 | Eliteserien | 3 | 2.09 | 1.29 | 6.3–5.0 | 57% | -0.09 |
| Swansea | Championship | 3 | 1.74 | 0.96 | 3.3–4.3 | 59% | -0.74 |
| Arsenal | Premier League | 5 | 1.76 | 0.98 | 4.8–3.0 | 60% | +0.24 |

All 599 teams' profiles: `data/match_stats/team_profiles.json`.

