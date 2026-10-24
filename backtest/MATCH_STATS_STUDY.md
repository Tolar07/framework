# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

603 matches, 2026-10-04 to 2026-10-23.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| FA Cup | 42 | 3.14 | — | — | — | — | — | — | — |
| League One | 36 | 2.69 | 2.93 | 28.6 | 8.5 | 4.6 | 11.6 | 3.6 | 0.32 |
| League Two | 36 | 2.58 | 2.77 | 25.7 | 7.6 | 3.5 | 9.8 | 4.2 | 0.34 |
| Championship | 35 | 2.83 | 2.99 | 28.2 | 8.5 | 5.1 | 10.2 | 0.2 | 0.33 |
| Europa League | 34 | 3.26 | 3.13 | 27.6 | 9.9 | 5.1 | 9.3 | 4.1 | 0.33 |
| Conference League | 31 | 2.84 | 3.03 | 29.1 | 9.4 | 4.8 | 9.8 | 3.8 | 0.30 |
| Champions League | 27 | 4.52 | 3.73 | 29.5 | 11.7 | 6.7 | 9.9 | 3.2 | 0.39 |
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| La Liga 2 | 26 | 2.65 | 2.70 | 25.4 | 8.5 | 4.3 | 10.6 | 5.4 | 0.31 |
| Ligue 2 | 22 | 2.95 | 2.66 | 25.2 | 8.9 | 4.0 | 10.1 | 3.8 | 0.33 |
| Serie B | 21 | 2.90 | 2.99 | 28.9 | 8.5 | 4.4 | 9.2 | 3.8 | 0.34 |
| Serie A | 21 | 3.19 | 3.27 | 29.0 | 10.4 | 5.6 | 9.2 | 3.3 | 0.31 |
| Premier League | 21 | 3.05 | 2.86 | 26.5 | 8.7 | 5.2 | 9.2 | 4.2 | 0.35 |
| La Liga | 19 | 3.26 | 2.86 | 28.4 | 10.2 | 4.0 | 10.3 | 5.3 | 0.32 |
| 2. Bundesliga | 18 | 2.33 | 2.67 | 29.3 | 9.7 | 3.7 | 11.1 | 3.7 | 0.24 |
| Allsvenskan | 18 | 2.72 | 2.67 | 28.5 | 9.5 | 2.9 | 11.1 | 0.3 | 0.29 |
| Eredivisie | 17 | 4.12 | 3.41 | 30.8 | 10.5 | 5.9 | 9.4 | 3.2 | 0.39 |
| Ligue 1 | 17 | 3.47 | 3.26 | 25.5 | 9.2 | 4.8 | 9.0 | 4.1 | 0.38 |
| Ekstraklasa | 16 | 3.31 | 3.02 | 30.1 | 9.3 | 5.2 | 10.1 | 3.8 | 0.36 |
| Turkish Super Lig | 15 | 2.53 | 3.05 | 28.0 | 9.9 | 4.7 | 10.2 | 3.7 | 0.26 |
| Bundesliga | 14 | 3.50 | 3.73 | 31.9 | 11.0 | 6.6 | 10.6 | 2.8 | 0.32 |
| National League | 12 | 3.25 | — | — | — | — | — | — | — |
| Austrian Bundesliga | 11 | 3.55 | 3.50 | 29.9 | 10.5 | 6.5 | 10.7 | 2.9 | 0.34 |
| Primeira Liga | 10 | 2.90 | 2.47 | 25.3 | 8.6 | 4.4 | 10.3 | 5.6 | 0.34 |
| Eliteserien | 10 | 3.80 | 3.38 | 31.2 | 10.8 | 4.1 | 10.1 | 3.9 | 0.35 |
| Scottish Premiership | 10 | 2.90 | 3.04 | 30.4 | 12.1 | 4.4 | 10.5 | 2.9 | 0.24 |
| HNL | 9 | 2.67 | — | 26.9 | 8.9 | 3.1 | 11.0 | 3.6 | 0.30 |
| Greek Super League | 9 | 3.56 | 2.78 | 25.2 | 8.6 | 4.3 | 8.3 | 4.1 | 0.42 |
| Belgian Pro League | 8 | 3.88 | 2.88 | 26.9 | 9.4 | 5.4 | 10.6 | 3.4 | 0.41 |
| Swiss Super League | 6 | 3.17 | 2.91 | 28.7 | 9.0 | 4.3 | 10.7 | 5.0 | 0.35 |
| Danish Superliga | 6 | 3.50 | 3.54 | 29.0 | 11.3 | 5.7 | 9.3 | 4.8 | 0.31 |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 536 | 61% | 22% | 18% |
| shots on target | 487 | 62% | 20% | 17% |
| big chances | 462 | 61% | 20% | 19% |
| possession | 526 | 40% | 22% | 39% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| Bournemouth | Europa League | 4 | 2.90 | 0.41 | 6.0–1.8 | 60% | -0.65 |
| Panathinaikos | Conference League | 4 | 3.13 | 0.66 | 6.2–1.8 | 63% | -0.13 |
| Bayern Munich | Champions League | 4 | 3.53 | 1.41 | 10.0–4.8 | 61% | -0.28 |
| Benfica | Europa League | 3 | 2.99 | 0.87 | 7.3–4.0 | 60% | +0.35 |
| Barcelona | La Liga | 3 | 2.63 | 0.60 | 9.7–3.0 | 74% | +1.37 |
| Mansfield | League One | 3 | 2.56 | 0.71 | 5.0–2.3 | 52% | -0.56 |
| Middlesbrough | Championship | 4 | 2.58 | 0.77 | 9.8–2.5 | 59% | +0.17 |
| Bodoe/Glimt | Champions League | 3 | 2.58 | 0.84 | 5.7–5.0 | 61% | -0.25 |
| Gornik Zabrze | Ekstraklasa | 3 | 2.38 | 0.74 | 6.7–3.7 | 48% | -0.71 |
| Stockport County FC | League One | 3 | 2.22 | 0.61 | 5.0–3.3 | 67% | -0.22 |
| SK Brann | Conference League | 3 | 2.75 | 1.15 | 8.0–3.0 | 73% | -0.75 |
| Club Brugge | Champions League | 3 | 3.92 | 2.49 | 6.7–7.3 | 56% | -0.26 |
| Leicester | League One | 3 | 2.17 | 0.78 | 6.7–3.7 | 66% | +0.16 |
| Inter | Serie A | 3 | 3.30 | 1.92 | 8.7–4.7 | 59% | -0.30 |
| Aston Villa | Champions League | 4 | 2.42 | 1.13 | 7.8–3.0 | 50% | +0.58 |
| Man City | Champions League | 3 | 2.52 | 1.26 | 5.7–4.0 | 66% | +1.15 |
| Huddersfield | League One | 3 | 2.44 | 1.24 | 6.3–3.3 | 39% | +0.22 |
| IF Elfsborg | Allsvenskan | 3 | 1.77 | 0.61 | 5.0–3.0 | 49% | +0.23 |
| GNK Dinamo Zagreb | Europa League | 3 | 2.35 | 1.23 | 5.7–4.7 | 51% | -1.02 |
| Barnet FC | League Two | 3 | 2.55 | 1.51 | 5.7–4.7 | 62% | -0.55 |
| Brest | Ligue 1 | 3 | 2.36 | 1.33 | 6.0–3.3 | 46% | -0.03 |
| Real Madrid | Champions League | 4 | 2.06 | 1.06 | 7.8–5.5 | 55% | +1.19 |
| Feyenoord | Eredivisie | 3 | 2.18 | 1.22 | 6.7–5.3 | 46% | +0.82 |
| Nancy | Ligue 2 | 3 | 1.64 | 0.68 | 4.7–2.7 | 53% | -0.30 |
| Roma | Champions League | 4 | 1.74 | 0.82 | 6.0–3.2 | 57% | +0.51 |
| Brighton | Conference League | 3 | 1.61 | 0.74 | 5.7–2.7 | 56% | +0.72 |
| Torino | Serie A | 3 | 1.85 | 0.99 | 4.7–4.0 | 46% | +0.82 |
| Nott'm Forest | Premier League | 3 | 2.18 | 1.34 | 4.3–3.7 | 45% | -1.51 |
| Port Vale | League Two | 3 | 1.65 | 0.83 | 4.3–3.0 | 48% | -0.65 |
| West Brom | Championship | 3 | 2.06 | 1.26 | 3.0–4.3 | 59% | -0.40 |
| Swansea | Championship | 3 | 1.74 | 0.96 | 3.3–4.3 | 59% | -0.74 |
| Reading | League One | 3 | 2.35 | 1.58 | 4.7–5.3 | 43% | -0.35 |
| Juventus | Europa League | 4 | 1.71 | 0.94 | 5.5–3.0 | 59% | -0.46 |
| Trabzonspor | Conference League | 3 | 1.97 | 1.21 | 7.0–4.7 | 48% | +0.36 |
| Lugano | Conference League | 3 | 2.26 | 1.53 | 6.3–5.7 | 47% | +1.74 |
| Girona | La Liga 2 | 3 | 1.16 | 0.43 | 4.3–2.0 | 49% | -0.16 |
| York City FC | League Two | 3 | 1.71 | 1.00 | 3.0–3.3 | 62% | -0.71 |
| Napoli | Champions League | 4 | 2.18 | 1.48 | 7.2–3.8 | 53% | -0.18 |
| Luton | League One | 3 | 2.22 | 1.55 | 6.0–4.7 | 51% | +0.11 |
| Vasteraas SK | Allsvenskan | 3 | 1.34 | 0.67 | 6.0–3.0 | 53% | -0.67 |

All 594 teams' profiles: `data/match_stats/team_profiles.json`.

