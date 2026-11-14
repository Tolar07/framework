# BASEBALL SECONDARY-MARKET VALUE WATCH (framework #569, baseball)

Record only. Each finished match's first SportyBet look; every side priced 1.60-2.60 that the model prices, graded from the recorded final score. Model: expected total runs = the mean total of EARLIER matches only (walk-forward, PENDING until 30), split by the first-look winner price (engine/baseball_events.from_total), negative-binomial runs. Cells: bets · landed vs model chance · return per unit at the first-look price. Edge = model chance x price - 1, above 30% dropped. CLV = first-look price x closing fair chance - 1. Several lines per match count (a market study, not the board). Written by `backtest/baseball_secondary_value.py`.

Matches with a final score: 12 · priced and graded: 0

NO DATA — PENDING (needs 30 earlier finished matches before a match is priced)
