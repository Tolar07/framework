# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

1051 matches, 2026-10-04 to 2026-11-02.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| League One | 65 | 2.74 | 2.94 | 28.8 | 8.9 | 4.8 | 12.1 | 3.6 | 0.31 |
| League Two | 61 | 2.97 | 2.73 | 26.0 | 8.2 | 3.8 | 9.6 | 3.9 | 0.36 |
| Championship | 56 | 2.86 | 2.99 | 28.0 | 8.6 | 4.8 | 10.5 | 1.5 | 0.33 |
| Serie B | 50 | 2.66 | 2.79 | 27.9 | 8.4 | 4.2 | 9.3 | 3.9 | 0.32 |
| Serie A | 50 | 3.46 | 3.22 | 28.8 | 10.0 | 5.4 | 9.7 | 3.1 | 0.35 |
| National League | 46 | 3.41 | — | — | — | — | — | — | — |
| La Liga 2 | 44 | 2.77 | 2.72 | 26.7 | 9.1 | 4.2 | 10.3 | 5.6 | 0.30 |
| FA Cup | 42 | 3.14 | — | — | — | — | — | — | — |
| Premier League | 40 | 2.55 | 2.71 | 26.8 | 8.0 | 4.8 | 9.9 | 4.2 | 0.32 |
| Allsvenskan | 39 | 2.54 | 2.52 | 27.9 | 9.0 | 3.0 | 11.2 | 1.9 | 0.28 |
| La Liga | 36 | 2.97 | 2.81 | 28.0 | 9.5 | 4.0 | 9.6 | 4.9 | 0.31 |
| Ligue 2 | 35 | 2.83 | 2.63 | 24.9 | 8.6 | 3.5 | 10.3 | 3.9 | 0.33 |
| 2. Bundesliga | 34 | 2.53 | 2.84 | 30.1 | 9.9 | 4.4 | 10.9 | 3.7 | 0.26 |
| Europa League | 34 | 3.26 | 3.13 | 27.6 | 9.9 | 5.1 | 9.3 | 4.1 | 0.33 |
| Eredivisie | 32 | 4.03 | 3.37 | 30.3 | 10.6 | 6.0 | 9.9 | 3.3 | 0.38 |
| Ligue 1 | 32 | 3.19 | 3.06 | 24.9 | 8.8 | 4.7 | 8.4 | 4.1 | 0.36 |
| Conference League | 31 | 2.84 | 3.03 | 29.1 | 9.4 | 4.8 | 9.8 | 3.8 | 0.30 |
| Turkish Super Lig | 30 | 3.07 | 3.09 | 27.6 | 10.1 | 5.1 | 9.6 | 3.7 | 0.30 |
| Ekstraklasa | 29 | 3.28 | 3.22 | 30.0 | 9.7 | 5.1 | 10.6 | 4.0 | 0.34 |
| Bundesliga | 28 | 3.29 | 3.48 | 30.0 | 9.9 | 5.7 | 10.2 | 3.4 | 0.33 |
| Primeira Liga | 27 | 2.48 | 2.34 | 26.0 | 8.1 | 3.7 | 9.1 | 4.6 | 0.31 |
| Champions League | 27 | 4.52 | 3.73 | 29.5 | 11.7 | 6.7 | 9.9 | 3.2 | 0.39 |
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| Belgian Pro League | 23 | 4.04 | 3.07 | 27.5 | 10.3 | 5.0 | 10.4 | 4.0 | 0.39 |
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
| expected goals | 933 | 59% | 22% | 20% |
| shots on target | 847 | 61% | 20% | 19% |
| big chances | 801 | 63% | 20% | 17% |
| possession | 919 | 39% | 21% | 40% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| Twente | Eredivisie | 3 | 3.20 | 0.82 | 8.3–3.3 | 64% | +0.80 |
| Bayern Munich | Bundesliga | 6 | 3.58 | 1.23 | 9.0–4.8 | 59% | -0.58 |
| TSV Hartberg | Austrian Bundesliga | 3 | 3.01 | 0.96 | 7.7–4.7 | 56% | -0.01 |
| Bournemouth | Premier League | 6 | 2.51 | 0.58 | 5.5–2.2 | 54% | -0.17 |
| Amed Sportif Faaliyetler | Turkish Super Lig | 4 | 2.60 | 0.70 | 5.5–2.5 | 53% | -0.10 |
| Panathinaikos | Greek Super League | 5 | 2.62 | 0.73 | 5.6–1.8 | 58% | +0.18 |
| Motor Lublin | Ekstraklasa | 3 | 2.81 | 1.00 | 10.0–3.7 | 56% | -0.15 |
| Middlesbrough | Championship | 5 | 2.41 | 0.69 | 9.0–2.0 | 59% | +0.39 |
| Molde | Eliteserien | 3 | 3.36 | 1.77 | 8.7–4.7 | 65% | +0.97 |
| Barcelona | La Liga | 5 | 2.47 | 0.90 | 8.4–3.4 | 72% | +1.33 |
| Stockport County FC | League One | 6 | 2.41 | 0.86 | 4.3–4.0 | 68% | -0.91 |
| Benfica | Primeira Liga | 5 | 2.47 | 0.95 | 5.8–4.4 | 61% | +0.13 |
| Inter | Serie A | 6 | 2.85 | 1.37 | 7.8–4.0 | 60% | -0.51 |
| Gornik Zabrze | Ekstraklasa | 4 | 2.11 | 0.64 | 5.0–2.8 | 49% | -0.86 |
| Genk | Belgian Pro League | 3 | 2.25 | 0.81 | 5.7–2.0 | 63% | -0.58 |
| Rangers | Scottish Premiership | 3 | 2.60 | 1.17 | 7.3–4.3 | 60% | +0.40 |
| Huddersfield | League One | 5 | 2.40 | 1.01 | 6.0–3.2 | 43% | +0.20 |
| Rosenborg BK | Eliteserien | 3 | 2.30 | 0.92 | 6.7–4.7 | 53% | +0.03 |
| Mansfield | League One | 5 | 2.22 | 0.85 | 5.0–3.4 | 52% | -0.22 |
| Hertha | 2. Bundesliga | 4 | 2.06 | 0.78 | 7.2–3.5 | 54% | -0.56 |
| Real Madrid | La Liga | 6 | 2.25 | 1.07 | 7.2–4.8 | 52% | +0.75 |
| Porto | Primeira Liga | 4 | 1.93 | 0.77 | 7.0–2.2 | 56% | -0.18 |
| Bodoe/Glimt | Eliteserien | 4 | 2.29 | 1.13 | 5.0–5.0 | 56% | +0.21 |
| Swansea | Championship | 4 | 2.00 | 0.85 | 4.8–3.5 | 60% | -0.25 |
| Viborg | Danish Superliga | 3 | 2.16 | 1.02 | 5.7–4.0 | 51% | -0.83 |
| SC Pisa | Serie B | 5 | 2.07 | 0.94 | 5.4–3.4 | 57% | -0.07 |
| Tottenham | Premier League | 4 | 1.67 | 0.55 | 5.2–2.5 | 66% | +0.33 |
| IF Elfsborg | Allsvenskan | 5 | 1.80 | 0.67 | 5.0–3.2 | 53% | +0.20 |
| GNK Dinamo Zagreb | HNL | 4 | 2.35 | 1.23 | 6.0–3.8 | 50% | -0.85 |
| Man City | Premier League | 5 | 2.15 | 1.08 | 6.0–3.4 | 65% | +0.25 |
| Laval | Ligue 2 | 3 | 1.81 | 0.74 | 4.3–2.3 | 58% | -0.48 |
| Leicester | League One | 6 | 2.08 | 1.03 | 6.2–4.2 | 64% | +0.08 |
| Club Brugge | Belgian Pro League | 5 | 3.17 | 2.17 | 6.6–5.6 | 59% | +0.43 |
| FC Sion | Swiss Super League | 3 | 2.08 | 1.10 | 2.3–3.0 | 58% | -1.41 |
| Benevento Calcio | Serie B | 5 | 1.92 | 0.96 | 5.6–2.2 | 53% | -0.32 |
| Sarpsborg 08 | Eliteserien | 4 | 2.45 | 1.51 | 6.5–5.2 | 60% | -0.45 |
| Port Vale | League Two | 5 | 1.75 | 0.88 | 4.8–3.6 | 49% | -0.35 |
| FC St. Pauli | 2. Bundesliga | 4 | 1.88 | 1.02 | 5.2–4.0 | 54% | -0.88 |
| BK Hacken | Allsvenskan | 5 | 1.70 | 0.87 | 7.0–4.2 | 55% | +0.10 |
| Como | Serie A | 5 | 1.78 | 0.97 | 5.4–3.0 | 63% | +0.02 |

All 607 teams' profiles: `data/match_stats/team_profiles.json`.

