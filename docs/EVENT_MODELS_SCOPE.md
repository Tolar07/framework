# Event models #6 — scope for the other sports (framework #560)

RECORD-ONLY scoping study. It changes no pick rule, stake, threshold, value bar, CLV gate or live switch.
Written 2026-11-12. What is checked and what is not is marked on every line: **[checked]** = read in this repo or
fetched on 2026-11-12; **[to confirm]** = the first record-only sweep of that sport's follow-up issue settles it.

## What could not be checked, and why
SportyBet's feed (`engine/multisport.py` `_FEED`) only answers when told which market ids to return (an empty
`marketId` gives HTTP 422, tried 2026-11-12). So the full list of event markets SportyBet prices per sport cannot be read
from outside; the "markets priced" column below is therefore the markets the framework already reads **[checked]** plus the
event markets that sport's bookmakers usually list **[to confirm]**. Each follow-up issue starts with a record-only sweep
(ask SportyBet for the sport's markets, log market id + name + line, never price or stake anything) so the list becomes
a fact before any model is built (HR35: missing reads PENDING, HR59: nothing invented).

## Ranking: (data available) x (markets priced)
Score 1-3 for each; ranked by the product, ties by how much of the model already exists.

| # | Sport | Event markets (SportyBet) | Free history source | Anchor model already here | Data | Markets | Score |
|---|-------|---------------------------|---------------------|---------------------------|------|---------|-------|
| 1 | Ice hockey | goals per period, total goals, team totals, shots on goal [to confirm] | NHL API `api-web.nhle.com` boxscores/landing, per-period shots and goals, no key [checked, 200 OK] | `engine/ice_hockey.py`, `engine/hockey_periods.py` (period split, #381) | 3 | 3 | 9 |
| 2 | Baseball | runs per innings, first 5 innings, team totals [checked: markets 251/256/258 read; innings to confirm] | MLB StatsAPI `statsapi.mlb.com` linescore by inning, no key [checked, 200 OK] | `engine/multisport.py` baseball Elo, `engine/mlb_pitcher.py` | 3 | 2 | 6 |
| 3 | American football | quarter / half totals, team totals [checked: 223/225 totals read; quarters to confirm] | nflverse play-by-play releases (github.com/nflverse/nflverse-data) [checked, 200 OK]; ESPN for NCAAF | NFL Elo + `backtest/NFL_MARGIN_STUDY.md` | 3 | 2 | 6 |
| 4 | Cricket | total runs, runs per over block, wickets, top batter [to confirm] | Cricsheet ball-by-ball (cricsheet.org/downloads) [checked, 200 OK] | cricket Elo (`CRICKET_STUDY.md`) | 3 | 2 | 6 |
| 5 | Snooker | total frames, correct score, centuries [markets 493/494 read: checked] | repo holds frames for 6,590 matches [checked]; centuries from cuetracker.net / snooker.org (200 OK) | snooker Elo, `data/snooker/results.json` | 2 | 2 | 4 |
| 6 | Volleyball | total points, set handicap, set totals [markets 188/237/238 read: checked] | Flashscore periods via `engine/match_facts.py` [checked in repo] | volleyball Elo | 2 | 2 | 4 |
| 7 | Darts | total 180s, most 180s, checkout over/under, legs [to confirm] | PDC site stats; DartsOrakel returned 403 on 2026-11-12 [checked]; repo holds sets/legs only (`data/darts/*.json`) | darts Elo (`DARTS_*_STUDY.md`) | 1 | 3 | 3 |
| 8 | Rugby | tries, penalties, half totals [to confirm] | ESPN scoreboard (scores only); no free try/penalty history found [to confirm] | rugby Elo + home edge | 1 | 2 | 2 |
| 9 | Table tennis | total points, set totals [markets 237/238 read: checked] | Flashscore periods; WTT/ITTF only (integrity leagues excluded, order 50) so little history | table tennis Elo | 1 | 1 | 1 |

Order of follow-up issues = the order above (ties: snooker before volleyball because its history is already in the repo; darts sits below them on score 3).

## Rules every follow-up inherits (from #560)
1. Record-only / shadow; label `shadow` until it beats the baseline; no board or bot change without the promotion gate.
2. Agree with the framework: the event model is conditioned on that sport's own win / total numbers; consistency checks are tests.
3. Beat the baseline (two teams' season averages) walk-forward with a one-matchday purge; report log loss / CRPS, bucket
   calibration and the number of things tried; write `backtest/<NAME>_STUDY.md`.
4. Graded after every game and kept (standing order 53).
5. Basketball parity: list the basketball twin for each new module in `config/sport_parity.json`.
6. Control Room reader in matchbook-agent in the same job (small PR there).
