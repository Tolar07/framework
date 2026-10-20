# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

499 matches, 2026-10-04 to 2026-10-19.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| Championship | 33 | 2.76 | 2.97 | 27.9 | 8.5 | 5.1 | 10.2 | 0.0 | 0.33 |
| FA Cup | 31 | 2.81 | — | — | — | — | — | — | — |
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| La Liga 2 | 25 | 2.64 | 2.72 | 25.5 | 8.3 | 4.3 | 10.7 | 5.4 | 0.32 |
| League One | 24 | 2.71 | 3.01 | 29.0 | 8.6 | 4.3 | 12.2 | 3.5 | 0.32 |
| League Two | 24 | 2.29 | 2.55 | 24.2 | 6.7 | 3.0 | 9.2 | 4.1 | 0.34 |
| Serie B | 20 | 2.95 | 3.02 | 28.7 | 8.6 | 4.5 | 9.3 | 3.9 | 0.35 |
| Serie A | 20 | 3.10 | 3.33 | 29.3 | 10.4 | 5.7 | 9.3 | 3.5 | 0.30 |
| Premier League | 20 | 3.10 | 2.87 | 26.6 | 8.7 | 5.2 | 9.4 | 4.3 | 0.36 |
| La Liga | 18 | 3.33 | 2.91 | 28.6 | 10.3 | 4.1 | 10.3 | 5.4 | 0.32 |
| Ligue 2 | 17 | 3.12 | 2.71 | 25.4 | 8.7 | 4.1 | 10.5 | 3.6 | 0.36 |
| Europa League | 17 | 3.18 | 3.31 | 27.3 | 9.6 | 5.8 | 9.1 | 4.2 | 0.33 |
| Eredivisie | 16 | 4.06 | 3.49 | 30.9 | 10.6 | 6.0 | 9.6 | 3.2 | 0.38 |
| Ligue 1 | 16 | 3.50 | 3.28 | 25.7 | 9.2 | 4.8 | 8.9 | 3.8 | 0.38 |
| 2. Bundesliga | 16 | 2.50 | 2.69 | 29.0 | 10.1 | 3.9 | 11.2 | 3.6 | 0.25 |
| Allsvenskan | 16 | 2.88 | 2.77 | 28.4 | 9.7 | 3.1 | 11.2 | 0.0 | 0.30 |
| Ekstraklasa | 15 | 3.40 | 3.04 | 29.7 | 9.2 | 5.3 | 10.1 | 3.8 | 0.37 |
| Conference League | 15 | 2.67 | 2.82 | 28.7 | 9.4 | 4.7 | 9.4 | 3.2 | 0.28 |
| Bundesliga | 14 | 3.50 | 3.73 | 31.9 | 11.0 | 6.6 | 10.6 | 2.8 | 0.32 |
| Turkish Super Lig | 14 | 2.50 | 3.09 | 28.0 | 9.9 | 4.7 | 9.9 | 3.4 | 0.25 |
| Champions League | 13 | 4.46 | 3.59 | 29.5 | 12.1 | 6.3 | 11.4 | 3.4 | 0.37 |
| National League | 12 | 3.25 | — | — | — | — | — | — | — |
| Eliteserien | 10 | 3.80 | 3.38 | 31.2 | 10.8 | 4.1 | 10.1 | 3.9 | 0.35 |
| Scottish Premiership | 10 | 2.90 | 3.04 | 30.4 | 12.1 | 4.4 | 10.5 | 2.9 | 0.24 |
| Austrian Bundesliga | 10 | 3.60 | 3.65 | 30.3 | 10.6 | 7.0 | 11.0 | 2.9 | 0.34 |
| HNL | 9 | 2.67 | — | 26.9 | 8.9 | 3.1 | 11.0 | 3.6 | 0.30 |
| Primeira Liga | 9 | 2.67 | 2.49 | 25.2 | 8.4 | 4.6 | 10.2 | 5.4 | 0.32 |
| Greek Super League | 9 | 3.56 | 2.78 | 25.2 | 8.6 | 4.3 | 8.3 | 4.1 | 0.42 |
| Belgian Pro League | 8 | 3.88 | 2.88 | 26.9 | 9.4 | 5.4 | 10.6 | 3.4 | 0.41 |
| Swiss Super League | 6 | 3.17 | 2.91 | 28.7 | 9.0 | 4.3 | 10.7 | 5.0 | 0.35 |
| Danish Superliga | 6 | 3.50 | 3.54 | 29.0 | 11.3 | 5.7 | 9.3 | 4.8 | 0.31 |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 443 | 63% | 21% | 17% |
| shots on target | 405 | 63% | 20% | 17% |
| big chances | 381 | 62% | 19% | 19% |
| possession | 438 | 39% | 21% | 40% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| Panathinaikos | Greek Super League | 3 | 3.33 | 0.60 | 6.3–1.7 | 65% | -1.00 |
| Bayern Munich | Bundesliga | 3 | 3.88 | 1.31 | 11.7–4.7 | 66% | -0.22 |
| Bournemouth | Premier League | 3 | 2.82 | 0.51 | 5.7–2.3 | 59% | -0.82 |
| Barcelona | La Liga | 3 | 2.63 | 0.60 | 9.7–3.0 | 74% | +1.37 |
| Inter | Serie A | 3 | 3.30 | 1.92 | 8.7–4.7 | 59% | -0.30 |
| Middlesbrough | Championship | 3 | 2.05 | 0.72 | 9.0–2.0 | 58% | -0.05 |
| Napoli | Serie A | 3 | 2.39 | 1.08 | 7.0–3.0 | 57% | -1.06 |
| Arsenal | Premier League | 3 | 1.72 | 0.61 | 5.0–2.3 | 63% | +0.28 |
| Aston Villa | Premier League | 3 | 2.32 | 1.26 | 7.0–3.0 | 49% | +0.68 |
| Feyenoord | Eredivisie | 3 | 2.18 | 1.22 | 6.7–5.3 | 46% | +0.82 |
| HNK Hajduk Split | HNL | 3 | 1.99 | 1.15 | 5.7–3.0 | 53% | -0.32 |
| Juventus | Serie A | 3 | 1.53 | 0.70 | 6.0–2.3 | 61% | -0.53 |
| West Brom | Championship | 3 | 2.06 | 1.26 | 3.0–4.3 | 59% | -0.40 |
| Real Madrid | La Liga | 3 | 1.71 | 0.92 | 6.7–5.3 | 52% | +1.29 |
| Swansea | Championship | 3 | 1.74 | 0.96 | 3.3–4.3 | 59% | -0.74 |
| Girona | La Liga 2 | 3 | 1.16 | 0.43 | 4.3–2.0 | 49% | -0.16 |
| Rennes | Ligue 1 | 3 | 2.46 | 1.81 | 8.7–5.0 | 58% | +0.54 |
| Wieczysta Krakow | Ekstraklasa | 3 | 1.97 | 1.37 | 4.3–5.7 | 55% | -0.30 |
| Wolves | Championship | 3 | 1.77 | 1.18 | 4.3–5.3 | 54% | -0.77 |
| Southampton | Championship | 3 | 1.86 | 1.30 | 3.0–3.3 | 55% | -1.19 |
| Besiktas Istanbul | Turkish Super Lig | 3 | 2.29 | 1.74 | 6.0–5.7 | 55% | -0.62 |
| Liverpool | Premier League | 3 | 1.94 | 1.40 | 6.7–3.3 | 53% | +0.73 |
| Cordoba | La Liga 2 | 3 | 1.97 | 1.48 | 5.0–2.7 | 56% | -0.30 |
| Atalanta | Serie A | 3 | 2.47 | 1.99 | 7.3–5.0 | 48% | +0.20 |
| Valladolid | La Liga 2 | 3 | 2.05 | 1.67 | 6.3–3.7 | 51% | +0.95 |
| Ceuta | La Liga 2 | 3 | 1.98 | 1.62 | 5.0–4.7 | 49% | -0.98 |
| Freiburg | Bundesliga | 3 | 1.41 | 1.05 | 5.0–2.7 | 54% | +0.59 |
| Wrexham | Championship | 3 | 1.17 | 0.81 | 4.3–2.7 | 53% | +0.83 |
| Marseille | Ligue 1 | 3 | 1.63 | 1.27 | 5.0–3.3 | 59% | +0.70 |
| Sturm Graz | Austrian Bundesliga | 3 | 2.12 | 1.78 | 5.7–3.3 | 46% | +0.55 |
| Portsmouth | Championship | 3 | 1.45 | 1.12 | 3.7–3.0 | 55% | -0.11 |
| Fenerbahce Istanbul | Turkish Super Lig | 3 | 2.18 | 1.86 | 5.3–7.0 | 55% | -0.18 |
| Mjallby AIF | Allsvenskan | 3 | 1.14 | 0.83 | 5.0–3.7 | 50% | -0.14 |
| Bristol City | Championship | 3 | 1.40 | 1.13 | 3.7–2.3 | 52% | -1.07 |
| Villarreal | La Liga | 3 | 1.40 | 1.14 | 5.0–2.7 | 55% | -0.40 |
| Bolton Wanderers | Championship | 3 | 2.09 | 1.85 | 4.7–3.0 | 48% | -0.75 |
| Ajax | Eredivisie | 3 | 2.00 | 1.80 | 6.7–5.0 | 56% | +0.33 |
| Roma | Serie A | 3 | 1.27 | 1.08 | 4.7–4.3 | 51% | +0.39 |
| Millwall | Championship | 3 | 1.42 | 1.26 | 4.3–2.0 | 58% | -0.42 |
| Lyon | Ligue 1 | 3 | 1.53 | 1.48 | 4.3–5.3 | 50% | +0.47 |

All 589 teams' profiles: `data/match_stats/team_profiles.json`.

