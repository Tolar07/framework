# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

164 matches, 2026-10-04 to 2026-10-10.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| National League | 12 | 3.25 | — | — | — | — | — | — | — |
| League One | 12 | 2.92 | 3.00 | 28.1 | 8.8 | 4.6 | 12.3 | 3.8 | 0.33 |
| League Two | 12 | 2.08 | 2.63 | 23.6 | 6.2 | 2.9 | 9.0 | 4.6 | 0.33 |
| Championship | 10 | 2.30 | 2.73 | 26.9 | 8.8 | 4.5 | 10.1 | 0.0 | 0.26 |
| La Liga 2 | 7 | 2.43 | 2.81 | 25.4 | 7.1 | 5.7 | 9.9 | 5.9 | 0.34 |
| Serie B | 7 | 2.57 | 2.86 | 28.3 | 7.3 | 4.4 | 8.9 | 3.7 | 0.35 |
| Ligue 2 | 7 | 1.86 | 2.59 | 23.9 | 8.7 | 3.9 | 11.1 | 4.4 | 0.21 |
| Bundesliga | 6 | 3.83 | 3.92 | 35.5 | 11.8 | 6.3 | 10.8 | 2.5 | 0.32 |
| Premier League | 6 | 3.33 | 2.71 | 25.0 | 9.3 | 5.5 | 7.5 | 5.0 | 0.36 |
| Belgian Pro League | 5 | 3.40 | 2.88 | 27.2 | 10.0 | 5.4 | 11.0 | 2.8 | 0.34 |
| Ligue 1 | 5 | 3.00 | 2.84 | 25.4 | 8.6 | 3.8 | 9.8 | 3.6 | 0.35 |
| 2. Bundesliga | 5 | 3.20 | 3.12 | 30.4 | 10.4 | 4.4 | 12.6 | 4.4 | 0.31 |
| Eredivisie | 4 | 3.00 | 3.19 | 28.8 | 8.5 | 6.2 | 11.5 | 3.5 | 0.35 |
| Ekstraklasa | 4 | 4.25 | 2.88 | 27.8 | 10.2 | 6.5 | 9.5 | 5.2 | 0.41 |
| Primeira Liga | 4 | 2.00 | 2.01 | 25.0 | 9.2 | 3.2 | 8.0 | 5.5 | 0.22 |
| La Liga | 4 | 2.25 | 2.30 | 26.8 | 9.5 | 3.5 | 10.8 | 6.2 | 0.24 |
| Allsvenskan | 4 | 3.75 | 3.11 | 25.2 | 8.8 | 2.2 | 11.8 | 0.0 | 0.43 |
| Turkish Super Lig | 4 | 2.50 | 2.87 | 32.0 | 10.8 | 4.2 | 9.5 | 4.0 | 0.23 |
| HNL | 3 | 3.33 | — | 28.0 | 8.3 | 4.0 | 10.3 | 3.7 | 0.40 |
| Eliteserien | 3 | 2.67 | 3.69 | 32.0 | 11.7 | 3.7 | 10.0 | 2.0 | 0.23 |
| Scottish Premiership | 3 | 2.67 | 2.80 | 33.0 | 12.0 | 2.7 | 11.3 | 2.7 | 0.22 |
| Serie A | 3 | 3.00 | 3.10 | 29.0 | 8.0 | 3.7 | 7.0 | 3.3 | 0.38 |
| Austrian Bundesliga | 3 | 1.67 | 3.28 | 32.0 | 8.7 | 6.7 | 11.7 | 3.0 | 0.19 |
| Swiss Super League | 3 | 4.33 | 2.78 | 29.3 | 9.7 | 5.0 | 12.0 | 4.7 | 0.45 |
| Greek Super League | 2 | 3.00 | 1.76 | 21.5 | 9.0 | 3.0 | 10.0 | 3.0 | 0.33 |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 148 | 58% | 26% | 16% |
| shots on target | 132 | 58% | 23% | 18% |
| big chances | 124 | 60% | 25% | 15% |
| possession | 144 | 37% | 25% | 38% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| none yet | | | | | | | |

All 324 teams' profiles: `data/match_stats/team_profiles.json`.

