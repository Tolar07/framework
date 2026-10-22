# BOTH SIDES STUDY — FOOTBALL: every side of every market, bet on or not

Written by `backtest/both_sides_study.py` (see its docstring). Every side of every market on every graded game is a yes/no record: SportyBet's margin-free chance vs what happened. Corrections are learned walk-forward — each day is judged only on what was learned BEFORE it.

4510 graded football games, 50567 yes/no records, 16 match days; 15 day(s) tested on what the days before them taught.

## Does learning improve the chances?

| | Brier score (lower is better) |
|---|---|
| SportyBet's chances, margin removed | 0.20704 |
| after learning | 0.20695 |

Over 50553 records on the tested days.

## Does learning improve the picks? (£1 a game, price 1.20–2.00, chance 50%+)

| Way of picking | picks | won | expected wins | £1 return ± 1 se |
|---|---|---|---|---|
| A likeliest outcome, plain chances | 4290 | 3232 (75.3%) | 3111 | -4.1% ± 0.8% |
| B likeliest outcome, learned chances | 4299 | 3232 (75.2%) | 3149 | -4.0% ± 0.9% |
| C learned chances, best value within 2 pts | 4299 | 3225 (75.0%) | 3143 | -3.8% ± 0.9% |

C picked a different outcome from A in 987 game(s).

## What has been learned (all days, groups with 50+ records)

| outcome @ price band | records | landed | price said | gap | learned shift now |
|---|---|---|---|---|---|
| Away or draw @3.00+ | 173 | 14.5% | 26.0% | -11.5% | -9.8% |
| Home or draw @2.00-3.00 | 247 | 30.8% | 40.1% | -9.3% | -8.3% |
| Home or draw @3.00+ | 60 | 16.7% | 25.9% | -9.2% | +0.0% |
| Away or draw @2.00-3.00 | 647 | 33.4% | 40.3% | -6.9% | -6.6% |
| Under 2.5 goals @3.00+ | 247 | 21.1% | 27.8% | -6.7% | -6.0% |
| Home or draw @1.60-2.00 | 455 | 46.6% | 52.9% | -6.3% | -5.9% |
| Away or draw @1.60-2.00 | 1082 | 46.1% | 52.3% | -6.2% | -6.0% |
| Under 3.5 goals @2.00-3.00 | 151 | 37.1% | 41.4% | -4.3% | +0.0% |
| Away or draw @1.40-1.60 | 1031 | 58.0% | 62.0% | -4.0% | -3.9% |
| Both teams to score — no @1.60-2.00 | 1317 | 46.6% | 50.5% | -3.9% | -3.8% |
| Under 2.5 goals @1.40-1.60 | 317 | 57.1% | 60.8% | -3.7% | +0.0% |
| Away to win @3.00+ | 2307 | 17.5% | 20.9% | -3.4% | -3.4% |
| Both teams to score — yes @1.20-1.40 | 189 | 66.1% | 68.7% | -2.6% | +0.0% |
| Both teams to score — no @1.40-1.60 | 188 | 57.4% | 59.9% | -2.4% | +0.0% |
| Under 1.5 goals @3.00+ | 2176 | 20.9% | 23.3% | -2.4% | -2.3% |
| Under 1.5 goals @2.00-3.00 | 584 | 33.0% | 35.1% | -2.0% | +0.0% |
| Both teams to score — yes @1.40-1.60 | 883 | 58.8% | 60.8% | -2.0% | +0.0% |
| Both teams to score — no @3.00+ | 83 | 26.5% | 28.5% | -2.0% | +0.0% |
| Draw @3.00+ | 4233 | 22.7% | 24.4% | -1.6% | -1.6% |
| Under 2.5 goals @2.00-3.00 | 1491 | 38.8% | 40.3% | -1.5% | +0.0% |
| Under 2.5 goals @1.60-2.00 | 1298 | 50.7% | 51.8% | -1.1% | +0.0% |
| Under 3.5 goals @1.40-1.60 | 973 | 61.7% | 62.5% | -0.9% | +0.0% |
| Under 3.5 goals @1.00-1.20 | 175 | 78.9% | 79.7% | -0.8% | +0.0% |
| Under 3.5 goals @1.20-1.40 | 1233 | 70.8% | 71.6% | -0.8% | +0.0% |
| Away to win @2.00-3.00 | 1437 | 36.9% | 37.2% | -0.3% | +0.0% |
| Over 2.5 goals @1.40-1.60 | 796 | 61.7% | 61.8% | -0.1% | +0.0% |
| Under 3.5 goals @1.60-2.00 | 651 | 53.8% | 53.8% | -0.0% | +0.0% |
| Over 3.5 goals @2.00-3.00 | 1664 | 38.1% | 38.1% | +0.0% | +0.0% |
| Home or draw @1.40-1.60 | 810 | 62.6% | 62.4% | +0.2% | +0.0% |
| Home to win @3.00+ | 955 | 22.1% | 21.7% | +0.4% | +0.0% |
| Over 2.5 goals @2.00-3.00 | 760 | 42.4% | 41.9% | +0.5% | +0.0% |
| Over 3.5 goals @1.40-1.60 | 66 | 62.1% | 61.5% | +0.6% | +0.0% |
| Draw @2.00-3.00 | 224 | 32.6% | 32.0% | +0.6% | +0.0% |
| Over 3.5 goals @3.00+ | 1105 | 26.7% | 26.0% | +0.7% | +0.0% |
| Both teams to score — no @2.00-3.00 | 1549 | 41.6% | 40.6% | +1.1% | +0.0% |
| Away or draw @1.20-1.40 | 781 | 72.5% | 70.8% | +1.6% | +0.0% |
| Over 1.5 goals @1.00-1.20 | 895 | 82.7% | 81.0% | +1.6% | +0.0% |
| Home or Away @1.20-1.40 | 3256 | 74.7% | 72.8% | +2.0% | +2.0% |
| Home to win @2.00-3.00 | 1696 | 40.7% | 38.6% | +2.1% | +0.0% |
| Over 1.5 goals @1.20-1.40 | 1558 | 74.9% | 72.6% | +2.3% | +2.2% |
| Both teams to score — yes @1.60-2.00 | 1692 | 54.6% | 52.1% | +2.5% | +2.5% |
| Home to win @1.00-1.20 | 107 | 85.0% | 82.1% | +2.9% | +0.0% |
| Away to win @1.40-1.60 | 157 | 64.3% | 61.3% | +3.1% | +0.0% |
| Over 2.5 goals @1.60-2.00 | 1484 | 55.5% | 52.4% | +3.1% | +3.0% |
| Home or draw @1.20-1.40 | 1469 | 75.3% | 71.6% | +3.7% | +3.7% |
| Away to win @1.60-2.00 | 396 | 55.1% | 51.0% | +4.0% | +0.0% |
| Home to win @1.40-1.60 | 423 | 65.2% | 61.2% | +4.1% | +0.0% |
| Away or draw @1.00-1.20 | 350 | 86.9% | 82.5% | +4.4% | +4.0% |
| Home or draw @1.00-1.20 | 1023 | 86.7% | 82.3% | +4.4% | +4.3% |
| Home to win @1.20-1.40 | 276 | 75.4% | 70.9% | +4.5% | +0.0% |
| Over 1.5 goals @1.40-1.60 | 281 | 67.6% | 63.1% | +4.5% | +0.0% |
| Home to win @1.60-2.00 | 1000 | 56.2% | 51.5% | +4.7% | +4.5% |
| Home or Away @1.00-1.20 | 787 | 86.1% | 81.1% | +5.0% | +4.8% |
| Over 3.5 goals @1.60-2.00 | 341 | 56.0% | 50.8% | +5.2% | +0.0% |
| Both teams to score — yes @2.00-3.00 | 377 | 48.0% | 42.2% | +5.8% | +5.4% |
| Over 2.5 goals @1.20-1.40 | 325 | 76.6% | 70.5% | +6.1% | +5.6% |
| Away to win @1.20-1.40 | 115 | 80.0% | 70.7% | +9.3% | +7.4% |

# BOTH SIDES STUDY — BASKETBALL: every side of every market, bet on or not

Written by `backtest/both_sides_study.py` (see its docstring). Every side of every market on every graded game is a yes/no record: SportyBet's margin-free chance vs what happened. Corrections are learned walk-forward — each day is judged only on what was learned BEFORE it.

892 graded basketball games, 5126 yes/no records, 16 match days; 15 day(s) tested on what the days before them taught.

## Does learning improve the chances?

| | Brier score (lower is better) |
|---|---|
| SportyBet's chances, margin removed | 0.23264 |
| after learning | 0.23264 |

Over 5120 records on the tested days.

## Does learning improve the picks? (£1 a game, price 1.20–2.00, chance 50%+)

| Way of picking | picks | won | expected wins | £1 return ± 1 se |
|---|---|---|---|---|
| A likeliest outcome, plain chances | 890 | 521 (58.5%) | 532 | -8.6% ± 2.6% |
| B likeliest outcome, learned chances | 890 | 521 (58.5%) | 532 | -8.6% ± 2.6% |
| C learned chances, best value within 2 pts | 890 | 518 (58.2%) | 531 | -9.0% ± 2.6% |

C picked a different outcome from A in 130 game(s).

## What has been learned (all days, groups with 50+ records)

| outcome @ price band | records | landed | price said | gap | learned shift now |
|---|---|---|---|---|---|
| winner away @1.40-1.60 | 75 | 53.3% | 62.8% | -9.5% | +0.0% |
| winner home @3.00+ | 119 | 16.0% | 20.0% | -4.0% | +0.0% |
| winner away @1.60-2.00 | 129 | 48.8% | 52.8% | -4.0% | +0.0% |
| total under @1.60-2.00 | 799 | 46.7% | 50.0% | -3.3% | +0.0% |
| winner home @1.20-1.40 | 166 | 70.5% | 72.0% | -1.5% | +0.0% |
| winner home @1.60-2.00 | 163 | 52.1% | 53.6% | -1.4% | +0.0% |
| handicap underdog @1.60-2.00 | 881 | 49.7% | 50.1% | -0.4% | +0.0% |
| winner home @1.00-1.20 | 169 | 85.8% | 85.6% | +0.2% | +0.0% |
| handicap favourite @1.60-2.00 | 879 | 50.3% | 49.9% | +0.4% | +0.0% |
| winner home @1.40-1.60 | 110 | 63.6% | 63.0% | +0.6% | +0.0% |
| winner away @3.00+ | 317 | 21.1% | 20.5% | +0.6% | +0.0% |
| winner away @1.00-1.20 | 70 | 85.7% | 85.0% | +0.8% | +0.0% |
| winner away @1.20-1.40 | 62 | 74.2% | 71.8% | +2.4% | +0.0% |
| winner away @2.00-3.00 | 229 | 42.4% | 39.9% | +2.5% | +0.0% |
| total over @1.60-2.00 | 800 | 53.4% | 50.0% | +3.3% | +0.0% |
| winner home @2.00-3.00 | 155 | 47.1% | 39.9% | +7.1% | +0.0% |

