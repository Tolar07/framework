# BOTH SIDES STUDY — FOOTBALL: every side of every market, bet on or not

Written by `backtest/both_sides_study.py` (see its docstring). Every side of every market on every graded game is a yes/no record: SportyBet's margin-free chance vs what happened. Corrections are learned walk-forward — each day is judged only on what was learned BEFORE it.

4854 graded football games, 59132 yes/no records, 18 match days; 17 day(s) tested on what the days before them taught.

## Does learning improve the chances?

| | Brier score (lower is better) |
|---|---|
| SportyBet's chances, margin removed | 0.20380 |
| after learning | 0.20370 |

Over 59118 records on the tested days.

## Does learning improve the picks? (£1 a game, price 1.20–2.00, chance 50%+)

| Way of picking | picks | won | expected wins | £1 return ± 1 se |
|---|---|---|---|---|
| A likeliest outcome, plain chances | 4619 | 3487 (75.5%) | 3353 | -4.0% ± 0.8% |
| B likeliest outcome, learned chances | 4628 | 3477 (75.1%) | 3397 | -4.2% ± 0.8% |
| C learned chances, best value within 2 pts | 4628 | 3463 (74.8%) | 3391 | -4.1% ± 0.8% |

C picked a different outcome from A in 1090 game(s).

## What has been learned (all days, groups with 50+ records)

| outcome @ price band | records | landed | price said | gap | learned shift now |
|---|---|---|---|---|---|
| Away or draw @3.00+ | 187 | 13.4% | 26.1% | -12.7% | -10.0% |
| Away Clean Sheet — yes @3.00+ | 51 | 11.8% | 21.4% | -9.7% | +0.0% |
| Home or draw @2.00-3.00 | 279 | 30.5% | 40.0% | -9.5% | -8.6% |
| Home or draw @3.00+ | 65 | 16.9% | 25.9% | -8.9% | +0.0% |
| Home Goals: 2 @3.00+ | 69 | 15.9% | 23.4% | -7.5% | +0.0% |
| Under 2.5 goals @3.00+ | 258 | 20.5% | 27.8% | -7.3% | -6.5% |
| Away or draw @2.00-3.00 | 695 | 33.8% | 40.3% | -6.5% | -6.2% |
| Home or draw @1.60-2.00 | 489 | 46.8% | 52.9% | -6.1% | -5.7% |
| Away or draw @1.60-2.00 | 1163 | 46.3% | 52.4% | -6.0% | -5.9% |
| Under 3.5 goals @2.00-3.00 | 154 | 36.4% | 41.4% | -5.0% | +0.0% |
| Both teams to score — no @1.60-2.00 | 1426 | 46.6% | 50.5% | -3.9% | -3.8% |
| Away to win @3.00+ | 2473 | 17.5% | 20.9% | -3.4% | -3.3% |
| Under 2.5 goals @1.40-1.60 | 340 | 57.6% | 60.8% | -3.2% | +0.0% |
| Both teams to score — no @1.40-1.60 | 202 | 56.9% | 59.9% | -3.0% | +0.0% |
| Away or draw @1.40-1.60 | 1114 | 59.1% | 62.0% | -2.9% | -2.9% |
| Teams to Score: Only Away @3.00+ | 60 | 11.7% | 14.4% | -2.7% | +0.0% |
| Teams to Score: Only Home @3.00+ | 50 | 16.0% | 18.5% | -2.5% | +0.0% |
| Under 1.5 goals @3.00+ | 2344 | 20.8% | 23.3% | -2.5% | -2.5% |
| Home Goals: 0 @3.00+ | 53 | 17.0% | 19.4% | -2.4% | +0.0% |
| Both teams to score — no @3.00+ | 84 | 26.2% | 28.5% | -2.3% | +0.0% |
| Both teams to score — yes @1.20-1.40 | 194 | 66.5% | 68.7% | -2.2% | +0.0% |
| Away Goals: 1 @2.00-3.00 | 58 | 32.8% | 34.8% | -2.1% | +0.0% |
| Under 1.5 goals @2.00-3.00 | 622 | 33.3% | 35.1% | -1.8% | +0.0% |
| Under 2.5 goals @2.00-3.00 | 1610 | 38.5% | 40.3% | -1.8% | +0.0% |
| Odd/Even: Even @1.60-2.00 | 89 | 49.4% | 50.9% | -1.4% | +0.0% |
| Draw @3.00+ | 4551 | 22.9% | 24.4% | -1.4% | -1.4% |
| Both teams to score — yes @1.40-1.60 | 938 | 59.4% | 60.8% | -1.4% | +0.0% |
| Under 2.5 goals @1.60-2.00 | 1389 | 50.5% | 51.8% | -1.2% | +0.0% |
| Draw (0:1) handicap @3.00+ | 60 | 21.7% | 22.7% | -1.0% | +0.0% |
| Under 3.5 goals @1.40-1.60 | 1053 | 61.5% | 62.6% | -1.0% | +0.0% |
| Under 3.5 goals @1.60-2.00 | 696 | 52.9% | 53.8% | -1.0% | +0.0% |
| Under 3.5 goals @1.20-1.40 | 1325 | 70.9% | 71.5% | -0.6% | +0.0% |
| Away Goals: 2 @3.00+ | 69 | 20.3% | 20.9% | -0.6% | +0.0% |
| Over 2.5 goals @1.40-1.60 | 849 | 61.5% | 61.8% | -0.3% | +0.0% |
| Away to win @2.00-3.00 | 1544 | 37.0% | 37.2% | -0.2% | +0.0% |
| Under 3.5 goals @1.00-1.20 | 185 | 79.5% | 79.6% | -0.2% | +0.0% |
| Home or draw @1.40-1.60 | 873 | 62.4% | 62.4% | -0.0% | +0.0% |
| Home to win @3.00+ | 1035 | 21.7% | 21.6% | +0.1% | +0.0% |
| Over 3.5 goals @2.00-3.00 | 1797 | 38.2% | 38.0% | +0.2% | +0.0% |
| Over 2.5 goals @2.00-3.00 | 809 | 42.0% | 41.8% | +0.2% | +0.0% |
| Over 3.5 goals @3.00+ | 1182 | 26.5% | 26.1% | +0.4% | +0.0% |
| Both teams to score — no @2.00-3.00 | 1657 | 41.1% | 40.6% | +0.5% | +0.0% |
| Away Goals: 3+ @3.00+ | 60 | 13.3% | 12.0% | +1.3% | +0.0% |
| Home to win @2.00-3.00 | 1825 | 40.0% | 38.6% | +1.4% | +0.0% |
| Teams to Score: None @3.00+ | 69 | 8.7% | 7.3% | +1.4% | +0.0% |
| Odd/Even: Odd @1.60-2.00 | 89 | 50.6% | 49.1% | +1.4% | +0.0% |
| Home or Away @1.20-1.40 | 3513 | 74.2% | 72.8% | +1.5% | +0.0% |
| Over 3.5 goals @1.40-1.60 | 68 | 63.2% | 61.5% | +1.7% | +0.0% |
| Over 1.5 goals @1.00-1.20 | 947 | 83.0% | 81.0% | +2.0% | +0.0% |
| Away or draw @1.20-1.40 | 838 | 72.9% | 70.8% | +2.1% | +0.0% |
| Over 1.5 goals @1.20-1.40 | 1690 | 75.0% | 72.7% | +2.3% | +2.2% |
| Home to win @1.00-1.20 | 115 | 84.3% | 81.9% | +2.4% | +0.0% |
| Draw @2.00-3.00 | 240 | 34.6% | 32.0% | +2.6% | +0.0% |
| Both teams to score — yes @1.60-2.00 | 1839 | 55.0% | 52.1% | +2.9% | +2.8% |
| Home or draw @1.20-1.40 | 1587 | 74.7% | 71.5% | +3.2% | +3.1% |
| Over 2.5 goals @1.60-2.00 | 1611 | 55.8% | 52.4% | +3.4% | +3.4% |
| Away or draw @1.00-1.20 | 393 | 86.3% | 82.5% | +3.7% | +0.0% |
| Home to win @1.40-1.60 | 449 | 65.3% | 61.2% | +4.0% | +0.0% |
| Away to win @1.60-2.00 | 427 | 55.3% | 51.2% | +4.1% | +0.0% |
| Away to win @1.40-1.60 | 171 | 65.5% | 61.3% | +4.2% | +0.0% |
| Home to win @1.60-2.00 | 1068 | 56.0% | 51.5% | +4.5% | +4.3% |
| Over 1.5 goals @1.40-1.60 | 300 | 67.7% | 63.1% | +4.6% | +0.0% |
| Home to win @1.20-1.40 | 299 | 75.6% | 70.9% | +4.6% | +0.0% |
| Home or draw @1.00-1.20 | 1097 | 87.2% | 82.3% | +4.9% | +4.8% |
| Both teams to score — yes @2.00-3.00 | 403 | 47.1% | 42.1% | +5.0% | +4.7% |
| Home or Away @1.00-1.20 | 854 | 86.5% | 81.1% | +5.4% | +5.2% |
| Over 3.5 goals @1.60-2.00 | 359 | 57.4% | 50.7% | +6.7% | +6.2% |
| Over 2.5 goals @1.20-1.40 | 344 | 77.3% | 70.5% | +6.9% | +6.3% |
| Home Goals: 3+ @3.00+ | 52 | 23.1% | 15.6% | +7.4% | +0.0% |
| Away to win @1.20-1.40 | 127 | 80.3% | 70.7% | +9.6% | +7.8% |

# BOTH SIDES STUDY — BASKETBALL: every side of every market, bet on or not

Written by `backtest/both_sides_study.py` (see its docstring). Every side of every market on every graded game is a yes/no record: SportyBet's margin-free chance vs what happened. Corrections are learned walk-forward — each day is judged only on what was learned BEFORE it.

1015 graded basketball games, 6684 yes/no records, 18 match days; 17 day(s) tested on what the days before them taught.

## Does learning improve the chances?

| | Brier score (lower is better) |
|---|---|
| SportyBet's chances, margin removed | 0.23277 |
| after learning | 0.23315 |

Over 6678 records on the tested days.

## Does learning improve the picks? (£1 a game, price 1.20–2.00, chance 50%+)

| Way of picking | picks | won | expected wins | £1 return ± 1 se |
|---|---|---|---|---|
| A likeliest outcome, plain chances | 1013 | 597 (58.9%) | 606 | -8.3% ± 2.5% |
| B likeliest outcome, learned chances | 1013 | 595 (58.7%) | 606 | -8.7% ± 2.5% |
| C learned chances, best value within 2 pts | 1013 | 591 (58.3%) | 605 | -9.1% ± 2.5% |

C picked a different outcome from A in 156 game(s).

## What has been learned (all days, groups with 50+ records)

| outcome @ price band | records | landed | price said | gap | learned shift now |
|---|---|---|---|---|---|
| handicap favourite @2.00-3.00 | 79 | 24.1% | 41.3% | -17.3% | -10.0% |
| total under @2.00-3.00 | 89 | 29.2% | 41.0% | -11.8% | -8.8% |
| winner away @1.40-1.60 | 87 | 55.2% | 62.8% | -7.6% | +0.0% |
| winner away @1.60-2.00 | 155 | 47.7% | 52.9% | -5.1% | +0.0% |
| winner home @3.00+ | 137 | 15.3% | 20.1% | -4.8% | +0.0% |
| total under @1.60-2.00 | 992 | 47.4% | 50.2% | -2.8% | +0.0% |
| winner home @1.00-1.20 | 191 | 84.3% | 85.4% | -1.1% | +0.0% |
| winner home @1.60-2.00 | 191 | 52.4% | 53.4% | -1.1% | +0.0% |
| handicap favourite @1.60-2.00 | 1050 | 49.9% | 50.1% | -0.2% | +0.0% |
| winner home @1.20-1.40 | 183 | 72.1% | 72.0% | +0.1% | +0.0% |
| winner home @1.40-1.60 | 123 | 63.4% | 63.0% | +0.4% | +0.0% |
| handicap underdog @1.60-2.00 | 1062 | 51.1% | 50.3% | +0.8% | +0.0% |
| winner away @3.00+ | 353 | 21.2% | 20.4% | +0.8% | +0.0% |
| handicap underdog @2.00-3.00 | 50 | 44.0% | 42.0% | +2.0% | +0.0% |
| winner away @1.00-1.20 | 78 | 87.2% | 85.1% | +2.1% | +0.0% |
| winner away @2.00-3.00 | 258 | 42.6% | 39.9% | +2.7% | +0.0% |
| total over @2.00-3.00 | 91 | 44.0% | 41.0% | +3.0% | +0.0% |
| total over @1.60-2.00 | 991 | 53.4% | 50.3% | +3.1% | +0.0% |
| winner away @1.20-1.40 | 73 | 75.3% | 71.9% | +3.5% | +0.0% |
| winner home @2.00-3.00 | 179 | 45.8% | 39.9% | +5.9% | +0.0% |

