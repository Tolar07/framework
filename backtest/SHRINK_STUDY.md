# SHRINK STUDY — 2026-10-05

**Question (Architect, 5 Oct):** the model rates a team after 4 matches and
starts promoted clubs from scratch. Does pulling every team's ratings toward
the league average predict better?

**Method:** `backtest/shrink_study.py`. Walk-forward like production: fit on
last season plus this season up to each cut, 240-day half-life, refit every
14 days, same 14 leagues and two seasons as `SELECTION_STUDY.md` — 3,650
matches. Shrinkage = `dixon_coles.fit(ridge=r)`: adds r × (sum of attack² and
centred defence²) to the fit, which moves teams with few matches most. Scored
on 1X2 log loss (lower is better).

| Ridge | All matches | Promoted / new clubs (990) | A side with < 10 games (242) | vs none | Leagues better |
|---|---|---|---|---|---|
| 0 (before) | 1.0168 | 1.0457 | 1.1274 | — | — |
| 1 | 1.0141 | 1.0373 | 1.0954 | −0.0027 ±0.0006 | 11 of 13 |
| **3 (adopted)** | **1.0127** | **1.0320** | **1.0721** | **−0.0041 ±0.0013** | **10 of 13** |
| 6 | 1.0136 | 1.0311 | 1.0599 | −0.0032 ±0.0020 | 9 of 13 |

**Decision:** ridge 3 in `orchestrator.RIDGE`, used for every domestic fit.
Stronger shrinkage keeps helping thin teams but starts to hurt established
ones. The cross-league (European) fit is unchanged.
