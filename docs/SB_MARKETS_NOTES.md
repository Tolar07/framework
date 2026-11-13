# SportyBet stat markets vs the event model (framework #567)

Record only. `engine/sb_markets.py`, called from `engine/stat_lines.py` (runs in Actions via `stat_lines.yml`; the
SportyBet event API refuses the UK PC).

Files written (framework-data, `data/stat_lines/`):
- `market_catalogue.json`: every market id seen, its name, mapped stat/scope (or null = UNMAPPED), a specifier example,
  outcome names, number of match pages seen. This is step 1 of the issue: read it after the first Actions run.
- `wide_pending.json`: per match, first and last look of every over/under line of a mapped stat, plus the value rows
  (model over chance, price, edge, `target` = edge >= 5% and price 1.60-2.60, `approx` for bookings).
- `graded/wide/<month>.jsonl`: the same rows after the match with the real count, `won` and `pnl` per unit
  (a count Flashscore does not carry stays PENDING; a red card leaves bookings ungraded).

Nothing here picks, stakes or blocks. Promotion is the Architect's gate; first judge by CLV (first vs last look) and by
the graded `pnl` of `target` rows per stat family, once enough matches exist.

Not yet built (needs the catalogue first): the exact SportyBet market ids for shots on target, offsides and team
totals (names are matched by keyword; anything unmatched stays UNMAPPED); team-total scope depends on the name saying
"home" / "away".

## Video method notes (untrusted; partly an app advert)
https://www.youtube.com/watch?v=8425wkRS-XI (Statto TV, "How To Predict Corners In Football"); the slide was checked
against the words.
- @ 00:35-01:39: last 10 league matches per team, split home/away, cups excluded. Candidate shadow: a last-10
  venue-split baseline beside `event_model` (which uses all history shrunk to the league mean).
- @ 02:44-03:17 (slide confirmed): team corners = (own won + opponent conceded) / 2, total = sum. Additive blend;
  ours is multiplicative. Test both walk-forward.
- @ 04:23-04:56: "tempo confirmation" thresholds (25 shots, 8 on target, xG 2.6): untested claims.
- @ 07:39-08:45: in-play "no corner in 12-15 min so the line drops": needs minute-level data; possible record-only
  study on the live tracker, not built.
(To be folded into `.claude/skills/sports-betting-edge/SKILL.md` by a session allowed to edit it.)
