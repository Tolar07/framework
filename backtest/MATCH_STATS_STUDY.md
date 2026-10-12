# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

222 matches, 2026-10-04 to 2026-10-11.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| National League | 12 | 3.25 | — | — | — | — | — | — | — |
| League One | 12 | 2.92 | 3.00 | 28.1 | 8.8 | 4.6 | 12.3 | 3.8 | 0.33 |
| League Two | 12 | 2.08 | 2.63 | 23.6 | 6.2 | 2.9 | 9.0 | 4.6 | 0.33 |
| La Liga 2 | 11 | 2.36 | 2.45 | 24.3 | 7.3 | 4.1 | 10.4 | 5.5 | 0.33 |
| Championship | 11 | 2.18 | 2.70 | 26.5 | 8.5 | 4.5 | 9.7 | 0.0 | 0.26 |
| Serie B | 10 | 2.90 | 3.03 | 28.7 | 8.1 | 4.5 | 8.6 | 3.8 | 0.36 |
| Premier League | 9 | 3.44 | 3.03 | 26.6 | 10.1 | 6.6 | 9.1 | 4.4 | 0.34 |
| Eredivisie | 8 | 3.38 | 3.15 | 29.9 | 8.6 | 6.2 | 10.4 | 3.4 | 0.39 |
| Belgian Pro League | 8 | 3.88 | 2.88 | 26.9 | 9.4 | 5.4 | 10.6 | 3.4 | 0.41 |
| Ligue 1 | 8 | 3.12 | 2.85 | 25.2 | 9.0 | 4.0 | 10.0 | 3.6 | 0.35 |
| La Liga | 8 | 3.12 | 2.73 | 27.6 | 9.5 | 3.8 | 11.2 | 5.6 | 0.33 |
| 2. Bundesliga | 8 | 2.75 | 2.80 | 29.2 | 10.4 | 4.1 | 13.1 | 4.0 | 0.27 |
| Serie A | 8 | 2.50 | 2.97 | 27.8 | 9.4 | 4.8 | 9.1 | 4.0 | 0.27 |
| Bundesliga | 7 | 3.71 | 3.57 | 32.6 | 10.9 | 6.1 | 10.6 | 2.4 | 0.34 |
| Primeira Liga | 7 | 2.29 | 2.33 | 24.6 | 8.4 | 4.1 | 10.9 | 5.4 | 0.27 |
| Ligue 2 | 7 | 1.86 | 2.59 | 23.9 | 8.7 | 3.9 | 11.1 | 4.4 | 0.21 |
| Ekstraklasa | 6 | 3.67 | 2.77 | 28.3 | 9.0 | 6.2 | 11.0 | 4.5 | 0.41 |
| Allsvenskan | 6 | 3.17 | 2.89 | 27.3 | 10.2 | 2.7 | 10.8 | 0.0 | 0.31 |
| Turkish Super Lig | 6 | 2.67 | 3.17 | 30.0 | 10.7 | 4.8 | 10.5 | 4.0 | 0.25 |
| Swiss Super League | 6 | 3.17 | 2.91 | 28.7 | 9.0 | 4.3 | 10.7 | 5.0 | 0.35 |
| HNL | 5 | 3.20 | — | 28.0 | 8.4 | 3.8 | 10.4 | 3.6 | 0.38 |
| Eliteserien | 5 | 3.20 | 3.64 | 34.8 | 12.0 | 4.4 | 10.8 | 2.8 | 0.27 |
| Scottish Premiership | 5 | 2.20 | 2.93 | 31.8 | 11.8 | 3.4 | 12.0 | 2.2 | 0.19 |
| Austrian Bundesliga | 5 | 3.00 | 3.49 | 29.6 | 9.8 | 8.0 | 10.2 | 2.6 | 0.31 |
| Greek Super League | 4 | 2.25 | 1.50 | 22.0 | 8.0 | 2.2 | 8.2 | 4.0 | 0.28 |
| Danish Superliga | 2 | 4.00 | 4.55 | 34.0 | 11.0 | 7.0 | 10.5 | 4.0 | 0.36 |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 202 | 61% | 23% | 15% |
| shots on target | 182 | 59% | 21% | 20% |
| big chances | 173 | 59% | 23% | 18% |
| possession | 201 | 38% | 22% | 40% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| Andorra | La Liga 2 | 3 | 1.18 | 0.91 | 3.7–4.0 | 47% | -0.85 |

All 436 teams' profiles: `data/match_stats/team_profiles.json`.

