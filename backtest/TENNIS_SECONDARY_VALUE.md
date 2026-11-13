# TENNIS SECONDARY-MARKET VALUE WATCH (framework #569, tennis)

Record only. Each singles match's first SportyBet look; every side priced 1.60-2.60 that the point-level serve/return model (engine/tennis_events.py, fitted to the same first-look match price) prices, graded from the recorded set scores. Cells: bets · landed vs model chance · return per unit at the first-look price. Edge = model chance x price - 1, above 30% dropped. CLV = first-look price x closing fair chance - 1. Several lines per match count (a market study, not the board). Written by `backtest/tennis_secondary_value.py`. PENDING: set 3+ winner, set score, tie-break yes/no (no board price), aces and double faults (no free serve data), doubles.

Matches graded: 177

| Market family | edge 5%+ | edge 10%+ | CLV (5%+) | status |
|---|---|---|---:|---|
| Total games | 377 · 47% vs 59% · -4.5% ± 5.3% | 342 · 46% vs 59% · -5.6% ± 5.6% | -5.5% | no steady edge |
| Set handicap +-1.5 | 64 · 55% vs 58% · +2.5% ± 12.0% | 28 · 46% vs 53% · -0.9% ± 20.7% | -6.8% | COLLECTING (64 of 200) |
| Set 1 winner | 1 · 0% vs 48% · -100.0% | — | -7.4% | COLLECTING (1 of 200) |
| Set 2 winner | — | — | PENDING | COLLECTING (0 of 200) |

