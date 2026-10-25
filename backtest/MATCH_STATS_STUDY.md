# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

712 matches, 2026-10-04 to 2026-10-24.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| League One | 48 | 2.67 | 2.84 | 28.1 | 8.7 | 4.6 | 12.1 | 3.5 | 0.31 |
| League Two | 47 | 2.70 | 2.75 | 25.6 | 7.9 | 3.7 | 9.9 | 3.9 | 0.34 |
| Championship | 45 | 2.76 | 3.00 | 28.6 | 8.4 | 4.9 | 10.7 | 1.0 | 0.33 |
| FA Cup | 42 | 3.14 | — | — | — | — | — | — | — |
| Europa League | 34 | 3.26 | 3.13 | 27.6 | 9.9 | 5.1 | 9.3 | 4.1 | 0.33 |
| Conference League | 31 | 2.84 | 3.03 | 29.1 | 9.4 | 4.8 | 9.8 | 3.8 | 0.30 |
| La Liga 2 | 30 | 2.60 | 2.72 | 25.8 | 8.7 | 4.1 | 10.9 | 5.6 | 0.30 |
| Serie B | 28 | 2.82 | 2.97 | 28.9 | 8.6 | 4.4 | 9.4 | 3.6 | 0.33 |
| Champions League | 27 | 4.52 | 3.73 | 29.5 | 11.7 | 6.7 | 9.9 | 3.2 | 0.39 |
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| Serie A | 25 | 3.20 | 3.20 | 28.6 | 10.1 | 5.5 | 9.4 | 3.4 | 0.32 |
| Premier League | 25 | 2.88 | 2.69 | 26.2 | 8.4 | 4.8 | 9.6 | 4.3 | 0.34 |
| Ligue 2 | 24 | 2.88 | 2.61 | 25.2 | 8.8 | 3.9 | 10.3 | 3.9 | 0.33 |
| La Liga | 23 | 3.13 | 2.91 | 29.2 | 10.2 | 4.0 | 10.3 | 5.4 | 0.31 |
| 2. Bundesliga | 22 | 2.41 | 2.76 | 30.0 | 9.9 | 4.0 | 11.1 | 3.7 | 0.24 |
| National League | 22 | 3.41 | — | — | — | — | — | — | — |
| Allsvenskan | 22 | 2.86 | 2.74 | 28.6 | 9.6 | 2.9 | 11.0 | 0.6 | 0.30 |
| Eredivisie | 20 | 4.20 | 3.43 | 31.1 | 10.7 | 6.0 | 9.8 | 3.0 | 0.39 |
| Ekstraklasa | 19 | 3.42 | 3.02 | 29.5 | 9.5 | 5.1 | 10.1 | 3.8 | 0.36 |
| Bundesliga | 19 | 3.21 | 3.53 | 30.5 | 10.3 | 5.9 | 10.3 | 2.9 | 0.31 |
| Ligue 1 | 18 | 3.44 | 3.16 | 24.8 | 8.9 | 4.7 | 8.9 | 4.2 | 0.39 |
| Turkish Super Lig | 17 | 2.65 | 3.02 | 28.4 | 9.8 | 4.6 | 10.0 | 3.7 | 0.27 |
| Scottish Premiership | 14 | 3.14 | 3.24 | 30.1 | 11.3 | 4.9 | 10.9 | 2.9 | 0.28 |
| Primeira Liga | 13 | 2.54 | 2.39 | 25.4 | 8.2 | 4.1 | 10.2 | 4.8 | 0.31 |
| Austrian Bundesliga | 13 | 3.23 | 3.37 | 30.4 | 10.2 | 5.9 | 11.2 | 2.6 | 0.32 |
| Belgian Pro League | 11 | 4.09 | 3.02 | 27.5 | 10.3 | 5.4 | 10.3 | 3.8 | 0.40 |
| HNL | 11 | 2.45 | — | 26.6 | 8.4 | 3.0 | 10.8 | 3.5 | 0.29 |
| Greek Super League | 11 | 3.36 | 2.56 | 24.0 | 7.9 | 3.9 | 7.8 | 4.3 | 0.43 |
| Eliteserien | 10 | 3.80 | 3.38 | 31.2 | 10.8 | 4.1 | 10.1 | 3.9 | 0.35 |
| Swiss Super League | 9 | 3.00 | 3.04 | 30.4 | 9.8 | 4.6 | 10.9 | 4.6 | 0.31 |
| Danish Superliga | 6 | 3.50 | 3.54 | 29.0 | 11.3 | 5.7 | 9.3 | 4.8 | 0.31 |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 633 | 59% | 22% | 18% |
| shots on target | 575 | 62% | 21% | 18% |
| big chances | 544 | 61% | 21% | 18% |
| possession | 619 | 39% | 22% | 39% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| Bournemouth | Europa League | 4 | 2.90 | 0.41 | 6.0–1.8 | 60% | -0.65 |
| Panathinaikos | Conference League | 4 | 3.13 | 0.66 | 6.2–1.8 | 63% | -0.13 |
| Bayern Munich | Champions League | 4 | 3.53 | 1.41 | 10.0–4.8 | 61% | -0.28 |
| Benfica | Europa League | 3 | 2.99 | 0.87 | 7.3–4.0 | 60% | +0.35 |
| Barcelona | La Liga | 3 | 2.63 | 0.60 | 9.7–3.0 | 74% | +1.37 |
| Middlesbrough | Championship | 4 | 2.58 | 0.77 | 9.8–2.5 | 59% | +0.17 |
| Stockport County FC | League One | 4 | 2.30 | 0.55 | 5.0–3.5 | 68% | -0.55 |
| Bodoe/Glimt | Champions League | 3 | 2.58 | 0.84 | 5.7–5.0 | 61% | -0.25 |
| Gornik Zabrze | Ekstraklasa | 3 | 2.38 | 0.74 | 6.7–3.7 | 48% | -0.71 |
| SK Brann | Conference League | 3 | 2.75 | 1.15 | 8.0–3.0 | 73% | -0.75 |
| Mansfield | League One | 4 | 2.38 | 0.80 | 5.2–3.0 | 50% | +0.12 |
| Huddersfield | League One | 4 | 2.59 | 1.06 | 6.0–3.2 | 41% | -0.09 |
| Club Brugge | Champions League | 3 | 3.92 | 2.49 | 6.7–7.3 | 56% | -0.26 |
| Rangers | Scottish Premiership | 3 | 2.60 | 1.17 | 7.3–4.3 | 60% | +0.40 |
| Inter | Serie A | 3 | 3.30 | 1.92 | 8.7–4.7 | 59% | -0.30 |
| Benevento Calcio | Serie B | 3 | 2.05 | 0.68 | 7.0–2.0 | 50% | +0.28 |
| Amed Sportif Faaliyetler | Turkish Super Lig | 3 | 1.81 | 0.61 | 5.0–2.7 | 52% | -0.15 |
| Man City | Premier League | 4 | 2.28 | 1.09 | 6.0–3.5 | 66% | +0.72 |
| Hertha | 2. Bundesliga | 3 | 1.78 | 0.63 | 7.0–3.0 | 57% | -0.78 |
| IF Elfsborg | Allsvenskan | 3 | 1.77 | 0.61 | 5.0–3.0 | 49% | +0.23 |
| GNK Dinamo Zagreb | Europa League | 3 | 2.35 | 1.23 | 5.7–4.7 | 51% | -1.02 |
| BK Hacken | Allsvenskan | 3 | 2.00 | 0.89 | 8.3–4.7 | 53% | +0.67 |
| Brest | Ligue 1 | 3 | 2.36 | 1.33 | 6.0–3.3 | 46% | -0.03 |
| Heidenheim | 2. Bundesliga | 3 | 2.15 | 1.14 | 7.0–5.3 | 50% | -1.48 |
| Real Madrid | Champions League | 4 | 2.06 | 1.06 | 7.8–5.5 | 55% | +1.19 |
| West Ham | Championship | 3 | 1.96 | 0.98 | 9.0–2.3 | 57% | +1.04 |
| Feyenoord | Eredivisie | 3 | 2.18 | 1.22 | 6.7–5.3 | 46% | +0.82 |
| Nancy | Ligue 2 | 3 | 1.64 | 0.68 | 4.7–2.7 | 53% | -0.30 |
| Leicester | League One | 4 | 1.89 | 0.98 | 6.2–4.8 | 64% | +0.11 |
| Brighton | Conference League | 3 | 1.61 | 0.74 | 5.7–2.7 | 56% | +0.72 |
| Torino | Serie A | 3 | 1.85 | 0.99 | 4.7–4.0 | 46% | +0.82 |
| Nott'm Forest | Premier League | 3 | 2.18 | 1.34 | 4.3–3.7 | 45% | -1.51 |
| Aston Villa | Premier League | 5 | 2.05 | 1.22 | 6.6–3.8 | 47% | +0.75 |
| Ascoli Calcio 1898 | Serie B | 3 | 2.01 | 1.21 | 4.7–5.0 | 59% | +0.32 |
| Swansea | Championship | 3 | 1.74 | 0.96 | 3.3–4.3 | 59% | -0.74 |
| Arsenal | Premier League | 5 | 1.76 | 0.98 | 4.8–3.0 | 60% | +0.24 |
| Juventus | Europa League | 4 | 1.71 | 0.94 | 5.5–3.0 | 59% | -0.46 |
| Trabzonspor | Conference League | 3 | 1.97 | 1.21 | 7.0–4.7 | 48% | +0.36 |
| Wolves | Championship | 5 | 1.62 | 0.88 | 3.6–3.4 | 57% | -0.62 |
| Lugano | Conference League | 3 | 2.26 | 1.53 | 6.3–5.7 | 47% | +1.74 |

All 595 teams' profiles: `data/match_stats/team_profiles.json`.

