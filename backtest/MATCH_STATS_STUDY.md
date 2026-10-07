# MATCH STATS STUDY — how the covered matches were played

Written by `backtest/match_stats_study.py` from `data/match_stats/` (FotMob post-match stats of every fixture the board rated). A stat FotMob didn't publish is left out, never counted as 0. A study, not a selector.

31 matches, 2026-10-04 to 2026-10-06.

## League styles (per match, both teams together)

| League | matches | goals | xG | shots | on target | big chances | corners | yellow | goals per shot on target |
|---|---|---|---|---|---|---|---|---|---|
| UEFA Nations League | 26 | 2.15 | 2.65 | 26.2 | 7.8 | 4.3 | 9.0 | 3.9 | 0.28 |
| La Liga 2 | 5 | 2.20 | 2.64 | 24.8 | 6.6 | 4.0 | 10.8 | 6.4 | 0.33 |

## Does the balance of play decide the match?

Every match where the two sides differed on the measure (draws included).

| The side with more … | matches | won | drew | lost |
|---|---|---|---|---|
| expected goals | 30 | 53% | 33% | 13% |
| shots on target | 29 | 48% | 34% | 17% |
| big chances | 24 | 62% | 33% | 4% |
| possession | 31 | 35% | 35% | 29% |

## Team profiles (3+ matches with xG), strongest xG balance first

Finishing = goals minus xG per match: a big positive number is usually luck that fades.

| Team | league | matches | xG for | xG against | shots on target for–against | possession | finishing |
|---|---|---|---|---|---|---|---|
| none yet | | | | | | | |

All 61 teams' profiles: `data/match_stats/team_profiles.json`.

