# Stats Sources - where the framework's statistics come from

> Written 2026-11-12 from live requests made that day (not from memory). The machine-readable copy is
> `config/stat_sources.json`; the owner is the data analyst (`.claude/agents/olp-xdv-data-analyst.md`).
> Related: [[Betting-Market-Study-Guide.md]], [[Rules.md]], [[STATE.md]].

The Architect, 2026-11-12, after posting five short stats videos: "do an extensive research on all of these
things ... use it for the framework ... Stats are key ... look for where you can get all the statistics."

## The finding

Everything in the five videos can be rebuilt from sources the framework can read free, and the widest one was
already being read for grading:

| What the videos rank | Where we get it | Seen on 2026-11-12 |
|---|---|---|
| Both teams to score, goals per game, by league | Flashscore day feed (every match in the world, one request a day) | 1,396 matches in 387 competitions on Sun 8 Nov |
| Goals before half-time, first-half scorers at home | The same feed's half-time score | on 1,361 of those 1,396 |
| When goals come (after the 76th / 80th minute) | Flashscore incidents feed: every goal's minute | goal minutes agreed with the half-time score on every match checked |
| Corners per match, how steady a team is | Flashscore stats feed: corners for the match and each half; FotMob; football-data.co.uk | stats on 20 of 40 matches spread over the day, corners on 18 |
| "Fair odds" against the market | Our own model against closing prices (football-data.co.uk) and SportyBet's live prices | - |

## Sources, by status

**In use**
- **Flashscore** day feed and match feeds: results, half-time, about 40 team stats by half (expected goals, shots,
  corners, cards, fouls, possession), goal minutes, form, head-to-head. Stats on top flights and most second
  tiers; third tiers and youth leagues give scores only. History reaches back 7 days, so it is collected daily
  (`engine/world_facts.py`).
- **FotMob**: match stats, shot maps, expected goals, lineups and unavailable players, team season numbers.
- **football-data.co.uk**: 22 divisions in 11 countries with half-time score, shots, corners, fouls, cards and
  closing prices, 20+ seasons back. 16 more countries with full-time score and closing 1X2 prices only.
- **ESPN**: 220 football competitions; a match summary has 28 team stats (corners won, shots, fouls, cards) and
  goal minutes. No expected goals, nothing by half. Good as a second source.
- **TheSportsDB**, **API-Football** (free key: old seasons only).

**Ready, not read yet**
- **OpenLigaDB**: German leagues, every goal's minute, many seasons back, open licence.
- **StatsBomb open data**: event-level data for chosen past competitions; for studying methods.
- **ClubElo** (was down when checked), **Understat** (six leagues; its page layout has changed and needs a new reader).

**Needs a key (the Architect's decision)**
- **football-data.org** (free key: 12 top competitions), **API-Football** current seasons (paid).

**Blocked: refuse automated reads, not used and not worked around**
- **Sofascore**, **FBref**, **SoccerSTATS**, **FootyStats** (FootyStats sells a data API; SoccerSTATS and FootyStats
  publish exactly the league rankings the videos show).

## What each video needs, and the caution

1. **League rankings (both teams to score, goal timing)**: world-facts archive. Description only until tested
   against the price; our second-half-of-season study found league-table background adds nothing over the price.
2. **Home teams' first-half goals**: world-facts archive. 6-13 home games is a small sample.
3. **Corner consistency**: world-facts detail + FotMob. A low spread over 20-36 games is partly luck; test that it
   persists.
4. **First-half goal filter ("hits 75.8%")**: a first-half goal is common in any match. The archive gives the
   real base rate per league; the filter is only worth something above it and above the price's break-even.
5. **Lower-league value ("fair 1.60, market 2.55")**: a gap that large usually means the model is missing
   something. Paper only, graded, split by size of the claimed gap.

Builds: framework issues #581 to #585. Nothing here changes a pick, stake or threshold.
