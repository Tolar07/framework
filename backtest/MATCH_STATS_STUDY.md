# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

436 matches, 2026-10-04 to 2026-10-17.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| Championship | 33 | 2.76 | 2.97 | 27.9 | 8.5 | 5.1 | 10.2 | 0.0 | 0.33 |
| FA Cup | 31 | 2.81 | — | — | — | — | — | — | — |
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| League One | 24 | 2.71 | 3.01 | 29.0 | 8.6 | 4.3 | 12.2 | 3.5 | 0.32 |
| League Two | 24 | 2.29 | 2.55 | 24.2 | 6.7 | 3.0 | 9.2 | 4.1 | 0.34 |
| La Liga 2 | 20 | 2.65 | 2.65 | 25.4 | 8.1 | 4.2 | 10.3 | 5.6 | 0.33 |
| Serie B | 17 | 3.00 | 2.97 | 27.8 | 8.2 | 4.4 | 9.1 | 3.9 | 0.36 |
| Europa League | 17 | 3.18 | 3.31 | 27.3 | 9.6 | 5.8 | 9.1 | 4.2 | 0.33 |
| Ligue 2 | 16 | 3.12 | 2.68 | 24.9 | 8.6 | 4.1 | 10.4 | 3.7 | 0.36 |
| Premier League | 15 | 3.20 | 2.95 | 26.9 | 9.4 | 5.9 | 9.3 | 4.6 | 0.34 |
| Conference League | 15 | 2.67 | 2.82 | 28.7 | 9.4 | 4.7 | 9.4 | 3.2 | 0.28 |
| 2. Bundesliga | 14 | 2.43 | 2.75 | 29.6 | 10.3 | 4.1 | 12.1 | 3.9 | 0.24 |
| Serie A | 14 | 2.86 | 3.26 | 29.6 | 10.2 | 5.5 | 9.4 | 3.6 | 0.28 |
| Bundesliga | 13 | 3.54 | 3.79 | 32.6 | 11.3 | 6.5 | 10.8 | 2.9 | 0.31 |
| La Liga | 13 | 3.15 | 2.83 | 27.9 | 9.9 | 4.2 | 11.0 | 5.7 | 0.32 |
| Champions League | 13 | 4.46 | 3.59 | 29.5 | 12.1 | 6.3 | 11.4 | 3.4 | 0.37 |
| Eredivisie | 12 | 3.83 | 3.36 | 30.8 | 9.8 | 6.0 | 9.5 | 3.7 | 0.39 |
| Ekstraklasa | 12 | 3.42 | 3.06 | 29.9 | 9.8 | 5.6 | 10.0 | 4.0 | 0.35 |
| National League | 12 | 3.25 | — | — | — | — | — | — | — |
| Turkish Super Lig | 12 | 2.50 | 3.09 | 28.2 | 9.8 | 4.7 | 10.2 | 3.2 | 0.26 |
| Ligue 1 | 11 | 3.09 | 2.83 | 25.1 | 8.5 | 4.1 | 9.2 | 3.5 | 0.37 |
| Allsvenskan | 10 | 3.00 | 2.81 | 26.8 | 9.5 | 3.1 | 10.1 | 0.0 | 0.32 |
| Scottish Premiership | 10 | 2.90 | 3.04 | 30.4 | 12.1 | 4.4 | 10.5 | 2.9 | 0.24 |
| Belgian Pro League | 8 | 3.88 | 2.88 | 26.9 | 9.4 | 5.4 | 10.6 | 3.4 | 0.41 |
| HNL | 8 | 2.88 | — | 27.1 | 9.1 | 3.2 | 11.4 | 3.5 | 0.32 |
| Primeira Liga | 8 | 2.62 | 2.44 | 24.9 | 8.2 | 4.5 | 10.9 | 5.4 | 0.32 |
| Eliteserien | 7 | 3.71 | 3.37 | 32.1 | 11.0 | 4.0 | 10.3 | 3.3 | 0.34 |
| Austrian Bundesliga | 7 | 3.43 | 3.70 | 28.7 | 10.1 | 7.7 | 11.6 | 2.7 | 0.34 |
| Swiss Super League | 6 | 3.17 | 2.91 | 28.7 | 9.0 | 4.3 | 10.7 | 5.0 | 0.35 |
| Greek Super League | 5 | 2.60 | 1.92 | 23.8 | 8.6 | 2.8 | 8.4 | 3.8 | 0.30 |
| Danish Superliga | 3 | 2.67 | 3.88 | 29.3 | 10.0 | 6.0 | 10.7 | 4.0 | 0.27 |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 381 | 63% | 22% | 15% |
| shots on target | 348 | 61% | 21% | 18% |
| big chances | 327 | 61% | 21% | 18% |
| possession | 378 | 40% | 22% | 39% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| Bayern Munich | Bundesliga | 3 | 3.88 | 1.31 | 11.7–4.7 | 66% | -0.22 |
| Barcelona | La Liga | 3 | 2.63 | 0.60 | 9.7–3.0 | 74% | +1.37 |
| Inter | Serie A | 3 | 3.30 | 1.92 | 8.7–4.7 | 59% | -0.30 |
| Middlesbrough | Championship | 3 | 2.05 | 0.72 | 9.0–2.0 | 58% | -0.05 |
| Napoli | Serie A | 3 | 2.39 | 1.08 | 7.0–3.0 | 57% | -1.06 |
| Aston Villa | Premier League | 3 | 2.32 | 1.26 | 7.0–3.0 | 49% | +0.68 |
| Feyenoord | Eredivisie | 3 | 2.18 | 1.22 | 6.7–5.3 | 46% | +0.82 |
| West Brom | Championship | 3 | 2.06 | 1.26 | 3.0–4.3 | 59% | -0.40 |
| Swansea | Championship | 3 | 1.74 | 0.96 | 3.3–4.3 | 59% | -0.74 |
| Wieczysta Krakow | Ekstraklasa | 3 | 1.97 | 1.37 | 4.3–5.7 | 55% | -0.30 |
| Wolves | Championship | 3 | 1.77 | 1.18 | 4.3–5.3 | 54% | -0.77 |
| Southampton | Championship | 3 | 1.86 | 1.30 | 3.0–3.3 | 55% | -1.19 |
| Liverpool | Premier League | 3 | 1.94 | 1.40 | 6.7–3.3 | 53% | +0.73 |
| Cordoba | La Liga 2 | 3 | 1.97 | 1.48 | 5.0–2.7 | 56% | -0.30 |
| Wrexham | Championship | 3 | 1.17 | 0.81 | 4.3–2.7 | 53% | +0.83 |
| Portsmouth | Championship | 3 | 1.45 | 1.12 | 3.7–3.0 | 55% | -0.11 |
| Fenerbahce Istanbul | Turkish Super Lig | 3 | 2.18 | 1.86 | 5.3–7.0 | 55% | -0.18 |
| Andorra | La Liga 2 | 3 | 1.18 | 0.91 | 3.7–4.0 | 47% | -0.85 |
| Bristol City | Championship | 3 | 1.40 | 1.13 | 3.7–2.3 | 52% | -1.07 |
| Villarreal | La Liga | 3 | 1.40 | 1.14 | 5.0–2.7 | 55% | -0.40 |
| Bolton Wanderers | Championship | 3 | 2.09 | 1.85 | 4.7–3.0 | 48% | -0.75 |
| Roma | Serie A | 3 | 1.27 | 1.08 | 4.7–4.3 | 51% | +0.39 |
| Millwall | Championship | 3 | 1.42 | 1.26 | 4.3–2.0 | 58% | -0.42 |
| Lille | Ligue 1 | 3 | 1.22 | 1.26 | 2.0–4.0 | 52% | -0.55 |
| Sheffield United | Championship | 3 | 1.29 | 1.34 | 3.7–3.3 | 45% | +0.71 |
| Charlton | Championship | 3 | 1.72 | 1.78 | 4.0–5.7 | 52% | -0.72 |
| PSV Eindhoven | Eredivisie | 3 | 1.37 | 1.57 | 3.7–5.7 | 53% | -0.37 |
| Burnley | Championship | 3 | 1.35 | 1.59 | 5.3–6.3 | 47% | +0.98 |
| Castellon | La Liga 2 | 3 | 1.39 | 1.65 | 4.0–4.3 | 64% | -0.06 |
| Mallorca | La Liga 2 | 3 | 1.03 | 1.30 | 3.7–4.3 | 52% | +0.31 |
| Cardiff City | Championship | 3 | 1.86 | 2.21 | 4.7–8.0 | 53% | +0.81 |
| GKS Katowice | Ekstraklasa | 3 | 1.44 | 1.90 | 4.7–4.3 | 47% | +0.56 |
| Watford | Championship | 3 | 1.63 | 2.29 | 6.7–7.0 | 48% | -0.63 |
| Viking FK | Eliteserien | 3 | 1.25 | 2.11 | 4.3–5.3 | 32% | +1.42 |
| Las Palmas | La Liga 2 | 3 | 0.72 | 1.63 | 2.3–6.7 | 43% | +0.28 |
| Lincoln City | Championship | 3 | 1.02 | 2.00 | 2.0–7.7 | 31% | -0.35 |
| Preston | Championship | 3 | 0.67 | 1.67 | 1.0–5.3 | 36% | -0.34 |
| Norwich | Championship | 3 | 0.72 | 1.88 | 3.7–4.7 | 47% | -0.38 |
| Blackburn | Championship | 3 | 1.15 | 2.44 | 3.7–4.0 | 40% | +0.51 |
| Stoke | Championship | 3 | 0.65 | 2.20 | 3.0–5.7 | 38% | +1.02 |

All 577 teams' profiles: `data/match_stats/team_profiles.json`.

