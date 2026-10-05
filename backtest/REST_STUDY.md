# REST STUDY — 2026-10-05

**Question (Architect, 5 Oct):** should rest days and fixture congestion move a
match's numbers? The laptop line had a ±10% "context" adjustment for them
(`legacy/laptop/engine/context.py`) that was never tested.

**Method:** `backtest/rest_study.py`. Walk-forward over the same 14 leagues and
two seasons as `SELECTION_STUDY.md`, 3,550 matches. For each match: days since
each side's previous league match, and league games in the previous 14 days.
Measured: actual (home win − away win) minus the model's (home − away chance).
If rest mattered beyond what the model already knows, this gap would move with
the rest difference.

## Results

| Rest, home minus away | Matches | Result vs model |
|---|---|---|
| home 3+ days less | 101 | +3.0 pts ±7.9 |
| home 1–2 less | 802 | +1.0 ±2.8 |
| equal | 1,701 | +1.9 ±2.0 |
| home 1–2 more | 827 | +2.4 ±2.7 |
| home 3+ days more | 119 | +1.5 ±7.2 |

Correlation between rest difference and the gap: 0.007 (t ≈ 0.4). Short rest
(3 days or fewer) on one side only, and league games in the last 14 days, show
nothing outside their error bars either.

## Decision

**Not adopted.** No rest or congestion effect beyond the model is detectable.
Limit: football-data has league matches only, so European and cup midweeks are
invisible here; a test that sees them needs a fixture history including cups.
Motivation (title race, relegation) cannot be tested this early in a season.
