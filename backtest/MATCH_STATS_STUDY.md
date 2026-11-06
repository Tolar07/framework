# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

1116 matches, 2026-10-04 to 2026-11-05.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| League One | 68 | 2.68 | 2.91 | 28.5 | 8.9 | 4.8 | 12.0 | 3.6 | 0.30 |
| Championship | 67 | 2.90 | 2.94 | 27.7 | 8.5 | 4.5 | 10.2 | 1.7 | 0.34 |
| League Two | 62 | 2.94 | 2.72 | 25.9 | 8.2 | 3.8 | 9.6 | 3.8 | 0.36 |
| Europa League | 51 | 3.10 | 3.05 | 27.3 | 9.9 | 4.9 | 9.2 | 4.2 | 0.31 |
| Serie B | 50 | 2.66 | 2.79 | 27.9 | 8.4 | 4.2 | 9.3 | 3.9 | 0.32 |
| Serie A | 50 | 3.46 | 3.22 | 28.8 | 10.0 | 5.4 | 9.7 | 3.1 | 0.35 |
| Conference League | 47 | 2.70 | 3.02 | 28.5 | 9.6 | 5.0 | 9.9 | 3.8 | 0.28 |
| National League | 46 | 3.41 | — | — | — | — | — | — | — |
| La Liga 2 | 44 | 2.77 | 2.72 | 26.7 | 9.1 | 4.2 | 10.3 | 5.6 | 0.30 |
| Champions League | 42 | 4.33 | 3.68 | 29.3 | 11.4 | 6.6 | 9.9 | 3.3 | 0.38 |
| FA Cup | 42 | 3.14 | — | — | — | — | — | — | — |
| Allsvenskan | 40 | 2.52 | 2.52 | 27.8 | 8.9 | 3.0 | 11.2 | 1.9 | 0.28 |
| Premier League | 40 | 2.55 | 2.71 | 26.8 | 8.0 | 4.8 | 9.9 | 4.2 | 0.32 |
| La Liga | 36 | 2.97 | 2.81 | 28.0 | 9.5 | 4.0 | 9.6 | 4.9 | 0.31 |
| Ligue 2 | 35 | 2.83 | 2.63 | 24.9 | 8.6 | 3.5 | 10.3 | 3.9 | 0.33 |
| 2. Bundesliga | 34 | 2.53 | 2.84 | 30.1 | 9.9 | 4.4 | 10.9 | 3.7 | 0.26 |
| Eredivisie | 32 | 4.03 | 3.37 | 30.3 | 10.6 | 6.0 | 9.9 | 3.3 | 0.38 |
| Ligue 1 | 32 | 3.19 | 3.06 | 24.9 | 8.8 | 4.7 | 8.4 | 4.1 | 0.36 |
| Turkish Super Lig | 30 | 3.07 | 3.09 | 27.6 | 10.1 | 5.1 | 9.6 | 3.7 | 0.30 |
| Ekstraklasa | 29 | 3.28 | 3.22 | 30.0 | 9.7 | 5.1 | 10.6 | 4.0 | 0.34 |
| Bundesliga | 28 | 3.29 | 3.48 | 30.0 | 9.9 | 5.7 | 10.2 | 3.4 | 0.33 |
| Primeira Liga | 27 | 2.48 | 2.34 | 26.0 | 8.1 | 3.7 | 9.1 | 4.6 | 0.31 |
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| Belgian Pro League | 24 | 4.04 | 3.04 | 27.4 | 10.2 | 5.0 | 10.2 | 4.0 | 0.39 |
| Scottish Premiership | 23 | 3.00 | 3.21 | 29.3 | 10.1 | 4.7 | 11.0 | 3.8 | 0.30 |
| Eliteserien | 20 | 4.10 | 3.76 | 32.3 | 10.4 | 4.3 | 10.9 | 4.0 | 0.39 |
| Austrian Bundesliga | 20 | 3.35 | 3.34 | 30.6 | 10.2 | 5.8 | 10.4 | 3.1 | 0.33 |
| Greek Super League | 19 | 3.37 | 2.64 | 25.2 | 8.7 | 4.2 | 9.1 | 4.2 | 0.39 |
| HNL | 18 | 2.67 | — | 25.2 | 8.4 | 3.5 | 10.1 | 3.9 | 0.32 |
| Swiss Super League | 18 | 3.44 | 3.28 | 31.1 | 10.2 | 5.1 | 10.8 | 4.6 | 0.34 |
| Danish Superliga | 12 | 3.58 | 3.86 | 30.6 | 11.8 | 6.2 | 8.8 | 4.2 | 0.30 |
| Turkish Cup | 4 | 2.50 | — | — | — | — | — | — | — |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 998 | 59% | 21% | 20% |
| shots on target | 905 | 61% | 20% | 19% |
| big chances | 856 | 62% | 20% | 18% |
| possession | 983 | 39% | 21% | 39% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| FC Twente Enschede | Conference League | 3 | 3.85 | 0.42 | 8.7–2.0 | 73% | -1.18 |
| Bayer Leverkusen | Europa League | 3 | 3.14 | 0.62 | 9.3–2.3 | 61% | -1.14 |
| Twente | Eredivisie | 3 | 3.20 | 0.82 | 8.3–3.3 | 64% | +0.80 |
| Bayern Munich | Champions League | 7 | 3.34 | 1.20 | 8.4–4.6 | 59% | -0.49 |
| TSV Hartberg | Austrian Bundesliga | 3 | 3.01 | 0.96 | 7.7–4.7 | 56% | -0.01 |
| Amed Sportif Faaliyetler | Turkish Super Lig | 4 | 2.60 | 0.70 | 5.5–2.5 | 53% | -0.10 |
| Panathinaikos | Conference League | 6 | 2.61 | 0.79 | 6.7–2.3 | 59% | +0.06 |
| Motor Lublin | Ekstraklasa | 3 | 2.81 | 1.00 | 10.0–3.7 | 56% | -0.15 |
| Bournemouth | Europa League | 7 | 2.48 | 0.80 | 6.0–2.3 | 54% | -0.05 |
| Como 1907 | Champions League | 3 | 2.52 | 0.85 | 8.3–4.0 | 55% | +2.48 |
| Molde | Eliteserien | 3 | 3.36 | 1.77 | 8.7–4.7 | 65% | +0.97 |
| Alkmaar | Europa League | 3 | 2.24 | 0.66 | 6.3–3.7 | 59% | +0.09 |
| Benfica | Europa League | 6 | 2.44 | 0.86 | 6.8–4.5 | 60% | +0.23 |
| Stockport County FC | League One | 6 | 2.41 | 0.86 | 4.3–4.0 | 68% | -0.91 |
| Barcelona | Champions League | 6 | 2.38 | 0.87 | 8.3–3.0 | 71% | +1.28 |
| Gornik Zabrze | Ekstraklasa | 4 | 2.11 | 0.64 | 5.0–2.8 | 49% | -0.86 |
| Union Gilloise | Europa League | 3 | 2.21 | 0.77 | 7.7–3.0 | 45% | +0.12 |
| Genk | Belgian Pro League | 3 | 2.25 | 0.81 | 5.7–2.0 | 63% | -0.58 |
| Rangers | Scottish Premiership | 3 | 2.60 | 1.17 | 7.3–4.3 | 60% | +0.40 |
| Real Madrid | Champions League | 7 | 2.42 | 1.03 | 7.3–4.9 | 55% | +0.58 |
| Rosenborg BK | Eliteserien | 3 | 2.30 | 0.92 | 6.7–4.7 | 53% | +0.03 |
| Middlesbrough | Championship | 6 | 2.15 | 0.82 | 7.8–2.3 | 59% | +0.18 |
| Inter | Champions League | 7 | 2.61 | 1.28 | 7.6–3.7 | 58% | -0.18 |
| Hertha | 2. Bundesliga | 4 | 2.06 | 0.78 | 7.2–3.5 | 54% | -0.56 |
| Porto | Champions League | 5 | 2.17 | 0.90 | 7.2–3.0 | 55% | +0.03 |
| Ferencvarosi Budapest | Europa League | 3 | 2.50 | 1.27 | 6.3–4.3 | 47% | +0.17 |
| Huddersfield | League One | 6 | 2.16 | 0.94 | 6.0–3.3 | 44% | +0.17 |
| Viborg | Danish Superliga | 3 | 2.16 | 1.02 | 5.7–4.0 | 51% | -0.83 |
| SC Pisa | Serie B | 5 | 2.07 | 0.94 | 5.4–3.4 | 57% | -0.07 |
| Tottenham | Premier League | 4 | 1.67 | 0.55 | 5.2–2.5 | 66% | +0.33 |
| IF Elfsborg | Allsvenskan | 5 | 1.80 | 0.67 | 5.0–3.2 | 53% | +0.20 |
| Man City | Champions League | 6 | 2.16 | 1.04 | 5.8–3.8 | 65% | +0.34 |
| Mansfield | League One | 6 | 2.04 | 0.96 | 4.7–3.2 | 53% | -0.38 |
| Laval | Ligue 2 | 3 | 1.81 | 0.74 | 4.3–2.3 | 58% | -0.48 |
| Leicester | League One | 6 | 2.08 | 1.03 | 6.2–4.2 | 64% | +0.08 |
| Swansea | Championship | 5 | 1.94 | 0.93 | 4.4–3.8 | 61% | -0.34 |
| FC Sion | Swiss Super League | 3 | 2.08 | 1.10 | 2.3–3.0 | 58% | -1.41 |
| Benevento Calcio | Serie B | 5 | 1.92 | 0.96 | 5.6–2.2 | 53% | -0.32 |
| Sarpsborg 08 | Eliteserien | 4 | 2.45 | 1.51 | 6.5–5.2 | 60% | -0.45 |
| Bodoe/Glimt | Champions League | 5 | 1.96 | 1.02 | 4.8–4.4 | 55% | +0.04 |

All 607 teams' profiles: `data/match_stats/team_profiles.json`.

