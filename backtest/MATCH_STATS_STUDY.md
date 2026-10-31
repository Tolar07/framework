# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

868 matches, 2026-10-04 to 2026-10-30.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| League One | 53 | 2.70 | 2.92 | 28.3 | 8.7 | 4.8 | 12.1 | 3.5 | 0.31 |
| League Two | 50 | 2.84 | 2.76 | 25.9 | 8.0 | 3.7 | 9.9 | 3.9 | 0.35 |
| Championship | 46 | 2.72 | 2.98 | 28.4 | 8.3 | 4.8 | 10.6 | 1.1 | 0.33 |
| FA Cup | 42 | 3.14 | — | — | — | — | — | — | — |
| Serie B | 40 | 2.75 | 2.82 | 28.2 | 8.5 | 4.2 | 9.4 | 3.9 | 0.32 |
| Serie A | 40 | 3.48 | 3.34 | 29.6 | 10.2 | 5.6 | 9.6 | 3.0 | 0.34 |
| La Liga 2 | 35 | 2.71 | 2.70 | 26.2 | 8.9 | 4.0 | 10.8 | 5.6 | 0.31 |
| National League | 35 | 3.43 | — | — | — | — | — | — | — |
| Europa League | 34 | 3.26 | 3.13 | 27.6 | 9.9 | 5.1 | 9.3 | 4.1 | 0.33 |
| Allsvenskan | 32 | 2.66 | 2.60 | 28.1 | 9.2 | 2.9 | 11.4 | 1.6 | 0.29 |
| Ligue 2 | 31 | 2.77 | 2.55 | 24.6 | 8.5 | 3.5 | 9.9 | 3.9 | 0.32 |
| Conference League | 31 | 2.84 | 3.03 | 29.1 | 9.4 | 4.8 | 9.8 | 3.8 | 0.30 |
| Premier League | 30 | 2.70 | 2.68 | 26.4 | 8.2 | 4.7 | 9.5 | 4.2 | 0.33 |
| La Liga | 28 | 2.89 | 2.77 | 28.4 | 9.7 | 3.9 | 10.0 | 5.2 | 0.30 |
| 2. Bundesliga | 27 | 2.52 | 2.74 | 29.4 | 9.7 | 4.0 | 11.1 | 3.8 | 0.26 |
| Champions League | 27 | 4.52 | 3.73 | 29.5 | 11.7 | 6.7 | 9.9 | 3.2 | 0.39 |
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| Ligue 1 | 26 | 3.23 | 3.08 | 24.7 | 9.0 | 4.5 | 8.8 | 4.3 | 0.36 |
| Eredivisie | 24 | 3.96 | 3.36 | 30.9 | 10.8 | 6.2 | 9.9 | 3.2 | 0.37 |
| Ekstraklasa | 24 | 3.08 | 3.01 | 29.5 | 9.3 | 4.9 | 10.3 | 3.9 | 0.33 |
| Turkish Super Lig | 23 | 2.83 | 3.09 | 27.6 | 10.0 | 5.0 | 9.9 | 3.8 | 0.28 |
| Bundesliga | 22 | 3.32 | 3.51 | 30.2 | 10.2 | 5.9 | 10.5 | 3.1 | 0.33 |
| Scottish Premiership | 20 | 3.10 | 3.17 | 30.0 | 10.5 | 4.7 | 10.9 | 3.5 | 0.30 |
| Primeira Liga | 19 | 2.63 | 2.53 | 27.2 | 8.4 | 4.0 | 9.4 | 4.9 | 0.31 |
| Belgian Pro League | 16 | 4.38 | 3.26 | 27.4 | 10.4 | 5.5 | 10.7 | 3.8 | 0.42 |
| Eliteserien | 16 | 3.81 | 3.48 | 32.1 | 10.2 | 3.9 | 10.9 | 3.8 | 0.37 |
| Austrian Bundesliga | 16 | 3.38 | 3.44 | 30.7 | 10.4 | 5.9 | 10.5 | 3.0 | 0.33 |
| HNL | 15 | 2.47 | — | 26.0 | 8.5 | 3.3 | 9.9 | 3.7 | 0.29 |
| Greek Super League | 14 | 3.50 | 2.65 | 24.6 | 8.7 | 4.3 | 8.1 | 4.4 | 0.40 |
| Swiss Super League | 12 | 2.75 | 3.02 | 30.9 | 9.6 | 4.3 | 10.7 | 4.6 | 0.29 |
| Danish Superliga | 10 | 3.70 | 3.62 | 29.5 | 11.4 | 5.4 | 8.4 | 4.5 | 0.32 |
| Turkish Cup | 4 | 2.50 | — | — | — | — | — | — | — |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 766 | 58% | 22% | 19% |
| shots on target | 701 | 60% | 22% | 19% |
| big chances | 659 | 62% | 21% | 17% |
| possession | 751 | 39% | 22% | 39% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| Panathinaikos | Conference League | 4 | 3.13 | 0.66 | 6.2–1.8 | 63% | -0.13 |
| Bournemouth | Premier League | 5 | 2.75 | 0.56 | 5.6–2.4 | 56% | -0.35 |
| Bayern Munich | Bundesliga | 5 | 3.40 | 1.33 | 9.8–4.6 | 60% | -0.20 |
| TSV Hartberg | Austrian Bundesliga | 3 | 3.01 | 0.96 | 7.7–4.7 | 56% | -0.01 |
| Middlesbrough | Championship | 4 | 2.58 | 0.77 | 9.8–2.5 | 59% | +0.17 |
| Motor Lublin | Ekstraklasa | 3 | 2.81 | 1.00 | 10.0–3.7 | 56% | -0.15 |
| Benfica | Primeira Liga | 4 | 2.69 | 1.04 | 6.2–4.5 | 60% | +0.31 |
| SK Brann | Conference League | 3 | 2.75 | 1.15 | 8.0–3.0 | 73% | -0.75 |
| Mansfield | League One | 4 | 2.38 | 0.80 | 5.2–3.0 | 50% | +0.12 |
| Inter | Serie A | 5 | 3.08 | 1.52 | 7.8–4.0 | 61% | -0.48 |
| SC Pisa | Serie B | 4 | 2.27 | 0.71 | 6.0–2.8 | 54% | +0.23 |
| Benevento Calcio | Serie B | 4 | 2.16 | 0.61 | 6.0–2.0 | 51% | -0.16 |
| Huddersfield | League One | 4 | 2.59 | 1.06 | 6.0–3.2 | 41% | -0.09 |
| Stockport County FC | League One | 5 | 2.33 | 0.84 | 4.6–3.8 | 67% | -0.93 |
| Gornik Zabrze | Ekstraklasa | 4 | 2.11 | 0.64 | 5.0–2.8 | 49% | -0.86 |
| Rangers | Scottish Premiership | 3 | 2.60 | 1.17 | 7.3–4.3 | 60% | +0.40 |
| Barcelona | La Liga | 4 | 2.27 | 0.93 | 8.8–3.5 | 71% | +0.98 |
| Amed Sportif Faaliyetler | Turkish Super Lig | 3 | 1.81 | 0.61 | 5.0–2.7 | 52% | -0.15 |
| Man City | Premier League | 4 | 2.28 | 1.09 | 6.0–3.5 | 66% | +0.72 |
| Hertha | 2. Bundesliga | 3 | 1.78 | 0.63 | 7.0–3.0 | 57% | -0.78 |
| Bodoe/Glimt | Eliteserien | 4 | 2.29 | 1.13 | 5.0–5.0 | 56% | +0.21 |
| IF Elfsborg | Allsvenskan | 4 | 1.79 | 0.68 | 5.0–3.2 | 49% | +0.21 |
| GNK Dinamo Zagreb | HNL | 4 | 2.35 | 1.23 | 6.0–3.8 | 50% | -0.85 |
| Leicester | League One | 5 | 2.08 | 0.99 | 6.0–4.2 | 64% | +0.12 |
| Laval | Ligue 2 | 3 | 1.81 | 0.74 | 4.3–2.3 | 58% | -0.48 |
| Brest | Ligue 1 | 3 | 2.36 | 1.33 | 6.0–3.3 | 46% | -0.03 |
| Heidenheim | 2. Bundesliga | 3 | 2.15 | 1.14 | 7.0–5.3 | 50% | -1.48 |
| Club Brugge | Belgian Pro League | 5 | 3.17 | 2.17 | 6.6–5.6 | 59% | +0.43 |
| West Ham | Championship | 3 | 1.96 | 0.98 | 9.0–2.3 | 57% | +1.04 |
| Nancy | Ligue 2 | 3 | 1.64 | 0.68 | 4.7–2.7 | 53% | -0.30 |
| Real Madrid | La Liga | 5 | 2.03 | 1.09 | 7.2–5.6 | 52% | +0.97 |
| Sparta Rotterdam | Eredivisie | 3 | 2.20 | 1.28 | 7.0–4.7 | 42% | +0.14 |
| Milan | Serie A | 4 | 2.29 | 1.39 | 5.5–4.5 | 60% | -0.29 |
| Lazio | Serie A | 4 | 1.93 | 1.04 | 5.8–3.2 | 58% | +1.57 |
| BK Hacken | Allsvenskan | 4 | 1.77 | 0.89 | 7.2–5.0 | 55% | +0.23 |
| Eldense | La Liga 2 | 3 | 2.15 | 1.28 | 3.3–5.0 | 52% | -0.49 |
| Nott'm Forest | Premier League | 3 | 2.18 | 1.34 | 4.3–3.7 | 45% | -1.51 |
| Aston Villa | Premier League | 5 | 2.05 | 1.22 | 6.6–3.8 | 47% | +0.75 |
| Goztepe Izmir | Turkish Super Lig | 3 | 1.99 | 1.17 | 5.7–4.3 | 40% | +0.67 |
| Sarpsborg 08 | Eliteserien | 3 | 2.09 | 1.29 | 6.3–5.0 | 57% | -0.09 |

All 607 teams' profiles: `data/match_stats/team_profiles.json`.

