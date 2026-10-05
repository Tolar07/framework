# HALF-TIME STUDY — 2026-10-05

**Question (Architect, 5 Oct):** can the engine price half-time markets?
SportyBet offers the full first- and second-half range on main-league games
(no corners or cards markets on its event pages, so those were not built).

**Method:** `backtest/half_study.py`. First-half goals = Poisson at the
match's full-time rates × the league's first-half share of goals (from earlier
matches only). Walk-forward like production (ridge 3, 240-day half-life,
refit every 14 days) on every league-season the other studies use, scored
against football-data's half-time scores. 4,074 matches.

| First-half market | Model | Base rates only |
|---|---|---|
| Result 1X2 (log loss) | **1.0473** | 1.0840 |
| Draw: said / landed | 40.9% / 39.8% | — |
| Over 0.5 goals (Brier) | 0.2014 | 0.2015 |
| Over 1.5 goals (Brier) | 0.2273 | 0.2286 |

## Decision

**First-half RESULT markets adopted** (`engine/half.py`): 1st Half 1X2,
Double Chance and Draw No Bet, chance anchored 75/25 on SportyBet's own
first-half 1X2 like every pick. They join the candidate pool for the
positive-value table and the alternative-market legs, never the main pick,
until they have a live record. **First-half goals markets not adopted:** the
model adds almost nothing over the league base rate.

Grading: Flashscore's feed gives each match's SECOND-half goals (fields BC,
BD); first half = full time − second half, which matched football-data's
half-time score in 37 of 37 matches checked.
