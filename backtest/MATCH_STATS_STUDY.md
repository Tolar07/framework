# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

50 matches, 2026-10-04 to 2026-10-09.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| La Liga 2 | 5 | 2.20 | 2.64 | 24.8 | 6.6 | 4.0 | 10.8 | 6.4 | 0.33 |
| Ligue 2 | 4 | 1.50 | 2.40 | 24.5 | 7.8 | 3.8 | 12.2 | 5.0 | 0.19 |
| Ekstraklasa | 2 | 4.00 | 3.02 | 31.0 | 10.0 | 7.5 | 11.5 | 4.5 | 0.40 |
| 2. Bundesliga | 2 | 0.50 | 2.19 | 25.0 | 5.0 | 3.0 | 10.0 | 3.5 | 0.10 |
| Eredivisie | 1 | 2.00 | 3.16 | 27.0 | 7.0 | 6.0 | 10.0 | 3.0 | 0.29 |
| Belgian Pro League | 1 | 4.00 | 2.23 | 28.0 | 10.0 | 7.0 | 18.0 | 3.0 | 0.40 |
| HNL | 1 | 3.00 | — | 24.0 | 8.0 | 4.0 | 10.0 | 2.0 | 0.38 |
| Bundesliga | 1 | 4.00 | 3.62 | 32.0 | 14.0 | 6.0 | 12.0 | 3.0 | 0.29 |
| Ligue 1 | 1 | 3.00 | 2.38 | 28.0 | 12.0 | 3.0 | 11.0 | 2.0 | 0.25 |
| Primeira Liga | 1 | 1.00 | 2.58 | 25.0 | 5.0 | 4.0 | 7.0 | 7.0 | 0.20 |
| La Liga | 1 | 2.00 | 1.77 | 24.0 | 11.0 | 2.0 | 10.0 | 9.0 | 0.18 |
| Serie B | 1 | 5.00 | 2.79 | 21.0 | 7.0 | 5.0 | 6.0 | 5.0 | 0.71 |
| National League | 1 | 2.00 | — | — | — | — | — | — | — |
| Eliteserien | 1 | 2.00 | 3.82 | 38.0 | 10.0 | 1.0 | 17.0 | 2.0 | 0.20 |
| Allsvenskan | 1 | 1.00 | 1.39 | 16.0 | 3.0 | 2.0 | 8.0 | 0.0 | 0.33 |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 47 | 57% | 30% | 13% |
| shots on target | 46 | 52% | 28% | 20% |
| big chances | 38 | 61% | 29% | 11% |
| possession | 47 | 34% | 28% | 38% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| none yet | | | | | | | |

All 99 teams' profiles: `data/match_stats/team_profiles.json`.

