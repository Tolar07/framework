# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

972 matches, 2026-10-04 to 2026-10-31.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| League One | 64 | 2.75 | 2.96 | 28.7 | 8.9 | 4.8 | 12.0 | 3.6 | 0.31 |
| League Two | 61 | 2.97 | 2.73 | 26.0 | 8.2 | 3.8 | 9.6 | 3.9 | 0.36 |
| Championship | 56 | 2.86 | 2.99 | 28.0 | 8.6 | 4.8 | 10.5 | 1.5 | 0.33 |
| National League | 46 | 3.41 | — | — | — | — | — | — | — |
| Serie B | 45 | 2.67 | 2.80 | 28.1 | 8.4 | 4.3 | 9.2 | 4.0 | 0.32 |
| Serie A | 43 | 3.56 | 3.35 | 29.2 | 10.4 | 5.7 | 9.6 | 3.1 | 0.34 |
| FA Cup | 42 | 3.14 | — | — | — | — | — | — | — |
| La Liga 2 | 38 | 2.66 | 2.65 | 26.4 | 8.8 | 3.9 | 10.6 | 5.6 | 0.30 |
| Premier League | 38 | 2.63 | 2.70 | 26.6 | 8.1 | 4.8 | 9.9 | 4.1 | 0.32 |
| Europa League | 34 | 3.26 | 3.13 | 27.6 | 9.9 | 5.1 | 9.3 | 4.1 | 0.33 |
| Ligue 2 | 33 | 2.79 | 2.61 | 24.9 | 8.7 | 3.5 | 10.0 | 3.9 | 0.32 |
| La Liga | 32 | 3.00 | 2.77 | 28.2 | 9.7 | 4.0 | 9.8 | 5.0 | 0.31 |
| Allsvenskan | 32 | 2.66 | 2.60 | 28.1 | 9.2 | 2.9 | 11.4 | 1.6 | 0.29 |
| 2. Bundesliga | 31 | 2.52 | 2.77 | 29.9 | 9.9 | 4.1 | 11.0 | 3.8 | 0.25 |
| Conference League | 31 | 2.84 | 3.03 | 29.1 | 9.4 | 4.8 | 9.8 | 3.8 | 0.30 |
| Eredivisie | 27 | 3.85 | 3.30 | 30.5 | 10.4 | 5.9 | 10.0 | 3.3 | 0.37 |
| Ekstraklasa | 27 | 3.22 | 3.17 | 30.0 | 9.7 | 5.0 | 10.3 | 3.9 | 0.33 |
| Bundesliga | 27 | 3.33 | 3.54 | 30.4 | 10.1 | 5.8 | 10.3 | 3.2 | 0.33 |
| Ligue 1 | 27 | 3.19 | 3.05 | 24.4 | 9.0 | 4.5 | 8.7 | 4.4 | 0.36 |
| Champions League | 27 | 4.52 | 3.73 | 29.5 | 11.7 | 6.7 | 9.9 | 3.2 | 0.39 |
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| Turkish Super Lig | 26 | 2.77 | 2.98 | 27.5 | 9.9 | 4.9 | 10.0 | 4.0 | 0.28 |
| Scottish Premiership | 22 | 3.05 | 3.18 | 29.3 | 10.1 | 4.6 | 10.9 | 3.8 | 0.30 |
| Primeira Liga | 21 | 2.71 | 2.52 | 27.1 | 8.4 | 4.0 | 9.2 | 4.5 | 0.32 |
| Belgian Pro League | 20 | 4.05 | 3.08 | 27.6 | 10.3 | 5.0 | 10.7 | 4.0 | 0.39 |
| Eliteserien | 18 | 3.94 | 3.59 | 32.4 | 10.3 | 4.1 | 10.9 | 3.9 | 0.38 |
| Austrian Bundesliga | 18 | 3.28 | 3.30 | 30.3 | 10.1 | 5.7 | 10.1 | 3.2 | 0.32 |
| HNL | 16 | 2.62 | — | 25.4 | 8.4 | 3.4 | 9.8 | 3.8 | 0.31 |
| Greek Super League | 15 | 3.60 | 2.64 | 25.0 | 9.0 | 4.4 | 8.7 | 4.6 | 0.40 |
| Swiss Super League | 15 | 2.80 | 3.17 | 31.1 | 9.5 | 4.5 | 10.3 | 4.5 | 0.30 |
| Danish Superliga | 10 | 3.70 | 3.62 | 29.5 | 11.4 | 5.4 | 8.4 | 4.5 | 0.32 |
| Turkish Cup | 4 | 2.50 | — | — | — | — | — | — | — |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 857 | 59% | 22% | 19% |
| shots on target | 779 | 60% | 21% | 19% |
| big chances | 733 | 62% | 21% | 17% |
| possession | 844 | 39% | 22% | 39% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| Panathinaikos | Conference League | 4 | 3.13 | 0.66 | 6.2–1.8 | 63% | -0.13 |
| Bayern Munich | Bundesliga | 6 | 3.58 | 1.23 | 9.0–4.8 | 59% | -0.58 |
| TSV Hartberg | Austrian Bundesliga | 3 | 3.01 | 0.96 | 7.7–4.7 | 56% | -0.01 |
| Bournemouth | Premier League | 6 | 2.51 | 0.58 | 5.5–2.2 | 54% | -0.17 |
| Motor Lublin | Ekstraklasa | 3 | 2.81 | 1.00 | 10.0–3.7 | 56% | -0.15 |
| Middlesbrough | Championship | 5 | 2.41 | 0.69 | 9.0–2.0 | 59% | +0.39 |
| Benfica | Primeira Liga | 4 | 2.69 | 1.04 | 6.2–4.5 | 60% | +0.31 |
| SK Brann | Conference League | 3 | 2.75 | 1.15 | 8.0–3.0 | 73% | -0.75 |
| Barcelona | La Liga | 5 | 2.47 | 0.90 | 8.4–3.4 | 72% | +1.33 |
| SC Pisa | Serie B | 4 | 2.27 | 0.71 | 6.0–2.8 | 54% | +0.23 |
| Stockport County FC | League One | 6 | 2.41 | 0.86 | 4.3–4.0 | 68% | -0.91 |
| Inter | Serie A | 6 | 2.85 | 1.37 | 7.8–4.0 | 60% | -0.51 |
| Gornik Zabrze | Ekstraklasa | 4 | 2.11 | 0.64 | 5.0–2.8 | 49% | -0.86 |
| Genk | Belgian Pro League | 3 | 2.25 | 0.81 | 5.7–2.0 | 63% | -0.58 |
| Rangers | Scottish Premiership | 3 | 2.60 | 1.17 | 7.3–4.3 | 60% | +0.40 |
| Huddersfield | League One | 5 | 2.40 | 1.01 | 6.0–3.2 | 43% | +0.20 |
| Rosenborg BK | Eliteserien | 3 | 2.30 | 0.92 | 6.7–4.7 | 53% | +0.03 |
| Mansfield | League One | 5 | 2.22 | 0.85 | 5.0–3.4 | 52% | -0.22 |
| Hertha | 2. Bundesliga | 4 | 2.06 | 0.78 | 7.2–3.5 | 54% | -0.56 |
| Amed Sportif Faaliyetler | Turkish Super Lig | 3 | 1.81 | 0.61 | 5.0–2.7 | 52% | -0.15 |
| Porto | Primeira Liga | 4 | 1.93 | 0.77 | 7.0–2.2 | 56% | -0.18 |
| Bodoe/Glimt | Eliteserien | 4 | 2.29 | 1.13 | 5.0–5.0 | 56% | +0.21 |
| Swansea | Championship | 4 | 2.00 | 0.85 | 4.8–3.5 | 60% | -0.25 |
| Tottenham | Premier League | 4 | 1.67 | 0.55 | 5.2–2.5 | 66% | +0.33 |
| IF Elfsborg | Allsvenskan | 4 | 1.79 | 0.68 | 5.0–3.2 | 49% | +0.21 |
| GNK Dinamo Zagreb | HNL | 4 | 2.35 | 1.23 | 6.0–3.8 | 50% | -0.85 |
| Man City | Premier League | 5 | 2.15 | 1.08 | 6.0–3.4 | 65% | +0.25 |
| Laval | Ligue 2 | 3 | 1.81 | 0.74 | 4.3–2.3 | 58% | -0.48 |
| Leicester | League One | 6 | 2.08 | 1.03 | 6.2–4.2 | 64% | +0.08 |
| Brest | Ligue 1 | 3 | 2.36 | 1.33 | 6.0–3.3 | 46% | -0.03 |
| Club Brugge | Belgian Pro League | 5 | 3.17 | 2.17 | 6.6–5.6 | 59% | +0.43 |
| FC Sion | Swiss Super League | 3 | 2.08 | 1.10 | 2.3–3.0 | 58% | -1.41 |
| Benevento Calcio | Serie B | 5 | 1.92 | 0.96 | 5.6–2.2 | 53% | -0.32 |
| Nancy | Ligue 2 | 3 | 1.64 | 0.68 | 4.7–2.7 | 53% | -0.30 |
| Real Madrid | La Liga | 5 | 2.03 | 1.09 | 7.2–5.6 | 52% | +0.97 |
| Sparta Rotterdam | Eredivisie | 3 | 2.20 | 1.28 | 7.0–4.7 | 42% | +0.14 |
| Lazio | Serie A | 4 | 1.93 | 1.04 | 5.8–3.2 | 58% | +1.57 |
| BK Hacken | Allsvenskan | 4 | 1.77 | 0.89 | 7.2–5.0 | 55% | +0.23 |
| Eldense | La Liga 2 | 3 | 2.15 | 1.28 | 3.3–5.0 | 52% | -0.49 |
| Port Vale | League Two | 5 | 1.75 | 0.88 | 4.8–3.6 | 49% | -0.35 |

All 607 teams' profiles: `data/match_stats/team_profiles.json`.

