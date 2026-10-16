# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

295 matches, 2026-10-04 to 2026-10-15.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| Championship | 22 | 2.91 | 2.96 | 27.2 | 8.9 | 5.3 | 10.6 | 0.0 | 0.33 |
| Europa League | 17 | 3.18 | 3.31 | 27.3 | 9.6 | 5.8 | 9.1 | 4.2 | 0.33 |
| La Liga 2 | 15 | 2.53 | 2.58 | 25.6 | 7.9 | 4.3 | 10.3 | 5.8 | 0.32 |
| Conference League | 15 | 2.67 | 2.82 | 28.7 | 9.4 | 4.7 | 9.4 | 3.2 | 0.28 |
| League One | 13 | 2.85 | 3.09 | 28.3 | 8.6 | 4.6 | 12.5 | 3.7 | 0.33 |
| Champions League | 13 | 4.46 | 3.59 | 29.5 | 12.1 | 6.3 | 11.4 | 3.4 | 0.37 |
| National League | 12 | 3.25 | — | — | — | — | — | — | — |
| League Two | 12 | 2.08 | 2.63 | 23.6 | 6.2 | 2.9 | 9.0 | 4.6 | 0.33 |
| Serie B | 10 | 2.90 | 3.03 | 28.7 | 8.1 | 4.5 | 8.6 | 3.8 | 0.36 |
| Serie A | 10 | 2.70 | 3.18 | 29.0 | 9.5 | 5.2 | 9.5 | 3.5 | 0.28 |
| Premier League | 10 | 3.60 | 3.06 | 26.7 | 10.3 | 6.4 | 9.0 | 4.2 | 0.35 |
| La Liga | 9 | 3.44 | 2.88 | 28.8 | 9.9 | 4.1 | 10.8 | 5.7 | 0.35 |
| Eredivisie | 8 | 3.38 | 3.15 | 29.9 | 8.6 | 6.2 | 10.4 | 3.4 | 0.39 |
| Belgian Pro League | 8 | 3.88 | 2.88 | 26.9 | 9.4 | 5.4 | 10.6 | 3.4 | 0.41 |
| Ekstraklasa | 8 | 3.75 | 2.93 | 28.2 | 9.1 | 5.9 | 10.4 | 4.2 | 0.41 |
| Ligue 1 | 8 | 3.12 | 2.85 | 25.2 | 9.0 | 4.0 | 10.0 | 3.6 | 0.35 |
| Primeira Liga | 8 | 2.62 | 2.44 | 24.9 | 8.2 | 4.5 | 10.9 | 5.4 | 0.32 |
| 2. Bundesliga | 8 | 2.75 | 2.80 | 29.2 | 10.4 | 4.1 | 13.1 | 4.0 | 0.27 |
| Ligue 2 | 8 | 2.38 | 2.69 | 24.6 | 9.0 | 4.1 | 10.5 | 4.2 | 0.26 |
| Allsvenskan | 8 | 3.00 | 2.99 | 28.1 | 10.0 | 3.0 | 10.9 | 0.0 | 0.30 |
| Bundesliga | 7 | 3.71 | 3.57 | 32.6 | 10.9 | 6.1 | 10.6 | 2.4 | 0.34 |
| Turkish Super Lig | 7 | 2.86 | 3.36 | 29.4 | 10.7 | 5.0 | 10.4 | 4.0 | 0.27 |
| Swiss Super League | 6 | 3.17 | 2.91 | 28.7 | 9.0 | 4.3 | 10.7 | 5.0 | 0.35 |
| HNL | 5 | 3.20 | — | 28.0 | 8.4 | 3.8 | 10.4 | 3.6 | 0.38 |
| Eliteserien | 5 | 3.20 | 3.64 | 34.8 | 12.0 | 4.4 | 10.8 | 2.8 | 0.27 |
| Scottish Premiership | 5 | 2.20 | 2.93 | 31.8 | 11.8 | 3.4 | 12.0 | 2.2 | 0.19 |
| Greek Super League | 5 | 2.60 | 1.92 | 23.8 | 8.6 | 2.8 | 8.4 | 3.8 | 0.30 |
| Austrian Bundesliga | 5 | 3.00 | 3.49 | 29.6 | 9.8 | 8.0 | 10.2 | 2.6 | 0.31 |
| Danish Superliga | 2 | 4.00 | 4.55 | 34.0 | 11.0 | 7.0 | 10.5 | 4.0 | 0.36 |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 275 | 64% | 21% | 15% |
| shots on target | 247 | 62% | 19% | 19% |
| big chances | 235 | 61% | 21% | 18% |
| possession | 271 | 39% | 21% | 40% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| Andorra | La Liga 2 | 3 | 1.18 | 0.91 | 3.7–4.0 | 47% | -0.85 |

All 509 teams' profiles: `data/match_stats/team_profiles.json`.

