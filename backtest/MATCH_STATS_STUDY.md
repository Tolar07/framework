# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

314 matches, 2026-10-04 to 2026-10-16.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| Championship | 23 | 2.91 | 2.97 | 27.5 | 9.0 | 5.3 | 10.5 | 0.0 | 0.32 |
| Europa League | 17 | 3.18 | 3.31 | 27.3 | 9.6 | 5.8 | 9.1 | 4.2 | 0.33 |
| La Liga 2 | 16 | 2.44 | 2.60 | 25.8 | 7.7 | 4.1 | 10.3 | 5.7 | 0.32 |
| Conference League | 15 | 2.67 | 2.82 | 28.7 | 9.4 | 4.7 | 9.4 | 3.2 | 0.28 |
| Ligue 2 | 13 | 3.00 | 2.72 | 24.8 | 9.0 | 4.0 | 10.2 | 3.6 | 0.33 |
| League One | 13 | 2.85 | 3.09 | 28.3 | 8.6 | 4.6 | 12.5 | 3.7 | 0.33 |
| Champions League | 13 | 4.46 | 3.59 | 29.5 | 12.1 | 6.3 | 11.4 | 3.4 | 0.37 |
| National League | 12 | 3.25 | — | — | — | — | — | — | — |
| League Two | 12 | 2.08 | 2.63 | 23.6 | 6.2 | 2.9 | 9.0 | 4.6 | 0.33 |
| Serie B | 11 | 3.00 | 3.03 | 29.0 | 8.3 | 4.5 | 8.9 | 3.7 | 0.36 |
| Serie A | 11 | 3.00 | 3.30 | 29.5 | 10.1 | 5.5 | 9.5 | 3.3 | 0.30 |
| La Liga | 10 | 3.30 | 2.78 | 28.3 | 9.8 | 3.9 | 10.5 | 5.6 | 0.34 |
| 2. Bundesliga | 10 | 2.40 | 2.78 | 28.8 | 10.3 | 4.2 | 12.2 | 4.1 | 0.23 |
| Premier League | 10 | 3.60 | 3.06 | 26.7 | 10.3 | 6.4 | 9.0 | 4.2 | 0.35 |
| Eredivisie | 9 | 3.44 | 3.13 | 28.7 | 8.6 | 5.9 | 9.8 | 3.1 | 0.40 |
| Ekstraklasa | 9 | 3.67 | 3.07 | 29.2 | 9.9 | 6.0 | 10.2 | 4.3 | 0.37 |
| Ligue 1 | 9 | 3.11 | 2.84 | 25.1 | 8.7 | 4.0 | 9.3 | 3.6 | 0.36 |
| Allsvenskan | 9 | 2.89 | 2.80 | 26.9 | 9.6 | 3.0 | 10.4 | 0.0 | 0.30 |
| Belgian Pro League | 8 | 3.88 | 2.88 | 26.9 | 9.4 | 5.4 | 10.6 | 3.4 | 0.41 |
| Primeira Liga | 8 | 2.62 | 2.44 | 24.9 | 8.2 | 4.5 | 10.9 | 5.4 | 0.32 |
| Turkish Super Lig | 8 | 2.88 | 3.13 | 28.9 | 10.4 | 4.5 | 10.4 | 4.0 | 0.28 |
| Bundesliga | 7 | 3.71 | 3.57 | 32.6 | 10.9 | 6.1 | 10.6 | 2.4 | 0.34 |
| HNL | 6 | 3.17 | — | 25.8 | 8.2 | 3.7 | 9.8 | 3.7 | 0.39 |
| Swiss Super League | 6 | 3.17 | 2.91 | 28.7 | 9.0 | 4.3 | 10.7 | 5.0 | 0.35 |
| Eliteserien | 5 | 3.20 | 3.64 | 34.8 | 12.0 | 4.4 | 10.8 | 2.8 | 0.27 |
| Scottish Premiership | 5 | 2.20 | 2.93 | 31.8 | 11.8 | 3.4 | 12.0 | 2.2 | 0.19 |
| Greek Super League | 5 | 2.60 | 1.92 | 23.8 | 8.6 | 2.8 | 8.4 | 3.8 | 0.30 |
| Austrian Bundesliga | 5 | 3.00 | 3.49 | 29.6 | 9.8 | 8.0 | 10.2 | 2.6 | 0.31 |
| Danish Superliga | 3 | 2.67 | 3.88 | 29.3 | 10.0 | 6.0 | 10.7 | 4.0 | 0.27 |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 292 | 63% | 22% | 15% |
| shots on target | 263 | 62% | 20% | 18% |
| big chances | 251 | 61% | 22% | 18% |
| possession | 290 | 39% | 21% | 39% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| Wieczysta Krakow | Ekstraklasa | 3 | 1.97 | 1.37 | 4.3–5.7 | 55% | -0.30 |
| Wolves | Championship | 3 | 1.77 | 1.18 | 4.3–5.3 | 54% | -0.77 |
| Cordoba | La Liga 2 | 3 | 1.97 | 1.48 | 5.0–2.7 | 56% | -0.30 |
| Andorra | La Liga 2 | 3 | 1.18 | 0.91 | 3.7–4.0 | 47% | -0.85 |
| Burnley | Championship | 3 | 1.35 | 1.59 | 5.3–6.3 | 47% | +0.98 |

All 512 teams' profiles: `data/match_stats/team_profiles.json`.

