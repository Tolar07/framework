# Darts Elo K-factor (learning speed) study

Made 2026-11-07 09:10 UTC by `backtest/darts_k_study.py` (framework#341). Record only.

Data: 691 PDC World Championship matches. Each match is scored from earlier matches only, then learned. `K` is how far a rating moves after one match.

No closing price exists for these matches: no edge is shown, only whether a different learning speed predicts winners better.

## Every try counted (10)

| K | Min games each | Scored | Brier | Log-loss | Favourite hit rate | Verdict |
|---|---|---|---|---|---|---|
| 8 | 8 | 94 | 0.2418 | 0.6766 | 0.617 | PENDING (needs 100 scored, has 94) |
| 16 | 8 | 94 | 0.2366 | 0.666 | 0.6064 | PENDING (needs 100 scored, has 94) |
| 24 | 8 | 94 | 0.2334 | 0.6593 | 0.6064 | PENDING (needs 100 scored, has 94) |
| 32 | 8 | 94 | 0.2316 | 0.6551 | 0.5957 | PENDING (needs 100 scored, has 94) |
| 48 | 8 | 94 | 0.23 | 0.6513 | 0.5957 | PENDING (needs 100 scored, has 94) |
| 8 | 3 | 300 | 0.2443 | 0.6816 | 0.5867 | no better than board K |
| 16 | 3 | 300 | 0.2406 | 0.6742 | 0.5833 | no better than board K |
| 24 | 3 | 300 | 0.2385 | 0.6697 | 0.58 | baseline (board K) |
| 32 | 3 | 300 | 0.2374 | 0.6672 | 0.5733 | lead (lower Brier than board K) |
| 48 | 3 | 300 | 0.2373 | 0.6665 | 0.5733 | lead (lower Brier than board K) |

Picking the best of several tries on the same matches flatters it; a lead needs confirming on new matches (the live shadow board) before it is even proposed to the Architect.

Record only: nothing here changes a stake, a bar or the live switch.
