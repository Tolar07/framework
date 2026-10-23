# BOTH SIDES STUDY — FOOTBALL: every side of every market, bet on or not

Written by `backtest/both_sides_study.py` (see its docstring). Every side of every market on every graded game is a yes/no record: SportyBet's margin-free chance vs what happened. Corrections are learned walk-forward — each day is judged only on what was learned BEFORE it.

4611 graded football games, 51837 yes/no records, 17 match days; 16 day(s) tested on what the days before them taught.

## Does learning improve the chances?

| | Brier score (lower is better) |
|---|---|
| SportyBet's chances, margin removed | 0.20706 |
| after learning | 0.20695 |

Over 51823 records on the tested days.

## Does learning improve the picks? (£1 a game, price 1.20–2.00, chance 50%+)

| Way of picking | picks | won | expected wins | £1 return ± 1 se |
|---|---|---|---|---|
| A likeliest outcome, plain chances | 4384 | 3307 (75.4%) | 3180 | -4.0% ± 0.8% |
| B likeliest outcome, learned chances | 4393 | 3304 (75.2%) | 3221 | -4.0% ± 0.8% |
| C learned chances, best value within 2 pts | 4393 | 3293 (75.0%) | 3215 | -3.9% ± 0.8% |

C picked a different outcome from A in 1015 game(s).

## What has been learned (all days, groups with 50+ records)

| outcome @ price band | records | landed | price said | gap | learned shift now |
|---|---|---|---|---|---|
| Away or draw @3.00+ | 176 | 14.2% | 26.0% | -11.8% | -10.0% |
| Home or draw @2.00-3.00 | 264 | 30.7% | 40.0% | -9.3% | -8.4% |
| Home or draw @3.00+ | 60 | 16.7% | 25.9% | -9.2% | +0.0% |
| Under 2.5 goals @3.00+ | 251 | 20.7% | 27.8% | -7.1% | -6.3% |
| Away or draw @2.00-3.00 | 662 | 33.8% | 40.3% | -6.4% | -6.2% |
| Away or draw @1.60-2.00 | 1098 | 46.1% | 52.3% | -6.3% | -6.1% |
| Home or draw @1.60-2.00 | 470 | 47.0% | 52.9% | -5.9% | -5.6% |
| Under 3.5 goals @2.00-3.00 | 152 | 36.8% | 41.4% | -4.6% | +0.0% |
| Both teams to score — no @1.60-2.00 | 1352 | 46.4% | 50.5% | -4.1% | -4.0% |
| Away or draw @1.40-1.60 | 1050 | 58.2% | 62.0% | -3.8% | -3.7% |
| Under 2.5 goals @1.40-1.60 | 323 | 57.3% | 60.8% | -3.5% | +0.0% |
| Away to win @3.00+ | 2346 | 17.5% | 20.9% | -3.4% | -3.3% |
| Both teams to score — no @1.40-1.60 | 191 | 56.5% | 59.9% | -3.3% | +0.0% |
| Under 1.5 goals @3.00+ | 2242 | 20.7% | 23.3% | -2.6% | -2.5% |
| Both teams to score — yes @1.20-1.40 | 190 | 66.3% | 68.7% | -2.4% | +0.0% |
| Under 1.5 goals @2.00-3.00 | 595 | 32.9% | 35.1% | -2.1% | +0.0% |
| Both teams to score — yes @1.40-1.60 | 900 | 58.8% | 60.8% | -2.0% | +0.0% |
| Both teams to score — no @3.00+ | 83 | 26.5% | 28.5% | -2.0% | +0.0% |
| Under 2.5 goals @2.00-3.00 | 1542 | 38.7% | 40.3% | -1.6% | +0.0% |
| Under 2.5 goals @1.60-2.00 | 1323 | 50.2% | 51.8% | -1.6% | +0.0% |
| Draw @3.00+ | 4322 | 22.8% | 24.4% | -1.6% | -1.6% |
| Under 3.5 goals @1.40-1.60 | 1012 | 61.5% | 62.6% | -1.1% | +0.0% |
| Under 3.5 goals @1.20-1.40 | 1258 | 70.5% | 71.6% | -1.1% | +0.0% |
| Away to win @2.00-3.00 | 1468 | 36.6% | 37.2% | -0.7% | +0.0% |
| Under 3.5 goals @1.00-1.20 | 177 | 79.1% | 79.7% | -0.6% | +0.0% |
| Over 2.5 goals @1.40-1.60 | 816 | 61.6% | 61.8% | -0.2% | +0.0% |
| Over 3.5 goals @2.00-3.00 | 1720 | 38.3% | 38.0% | +0.2% | +0.0% |
| Under 3.5 goals @1.60-2.00 | 662 | 54.1% | 53.8% | +0.3% | +0.0% |
| Home to win @3.00+ | 991 | 22.0% | 21.7% | +0.3% | +0.0% |
| Over 2.5 goals @2.00-3.00 | 772 | 42.2% | 41.9% | +0.4% | +0.0% |
| Home or draw @1.40-1.60 | 829 | 63.0% | 62.4% | +0.5% | +0.0% |
| Over 3.5 goals @3.00+ | 1123 | 26.8% | 26.0% | +0.8% | +0.0% |
| Both teams to score — no @2.00-3.00 | 1593 | 41.7% | 40.6% | +1.1% | +0.0% |
| Over 3.5 goals @1.40-1.60 | 67 | 62.7% | 61.5% | +1.2% | +0.0% |
| Away or draw @1.20-1.40 | 802 | 72.3% | 70.8% | +1.5% | +0.0% |
| Over 1.5 goals @1.00-1.20 | 917 | 82.8% | 81.0% | +1.7% | +0.0% |
| Home or Away @1.20-1.40 | 3334 | 74.5% | 72.8% | +1.8% | +1.8% |
| Draw @2.00-3.00 | 230 | 33.9% | 32.0% | +1.9% | +0.0% |
| Home to win @2.00-3.00 | 1724 | 40.7% | 38.6% | +2.1% | +0.0% |
| Over 1.5 goals @1.20-1.40 | 1607 | 75.2% | 72.7% | +2.5% | +2.4% |
| Both teams to score — yes @1.60-2.00 | 1751 | 54.8% | 52.1% | +2.6% | +2.6% |
| Home to win @1.00-1.20 | 108 | 85.2% | 82.1% | +3.1% | +0.0% |
| Away to win @1.40-1.60 | 164 | 64.6% | 61.4% | +3.3% | +0.0% |
| Home or draw @1.20-1.40 | 1494 | 75.2% | 71.6% | +3.6% | +3.5% |
| Over 2.5 goals @1.60-2.00 | 1536 | 56.1% | 52.4% | +3.7% | +3.6% |
| Home to win @1.40-1.60 | 431 | 65.0% | 61.2% | +3.8% | +0.0% |
| Away to win @1.60-2.00 | 409 | 55.0% | 51.1% | +3.9% | +0.0% |
| Away or draw @1.00-1.20 | 369 | 87.0% | 82.5% | +4.5% | +4.2% |
| Home or draw @1.00-1.20 | 1040 | 86.8% | 82.3% | +4.5% | +4.4% |
| Home to win @1.60-2.00 | 1016 | 56.1% | 51.5% | +4.6% | +4.4% |
| Home to win @1.20-1.40 | 282 | 75.5% | 70.9% | +4.6% | +0.0% |
| Over 1.5 goals @1.40-1.60 | 286 | 67.8% | 63.1% | +4.8% | +0.0% |
| Home or Away @1.00-1.20 | 802 | 86.2% | 81.1% | +5.0% | +4.9% |
| Over 3.5 goals @1.60-2.00 | 344 | 55.8% | 50.8% | +5.0% | +0.0% |
| Over 2.5 goals @1.20-1.40 | 329 | 76.6% | 70.5% | +6.0% | +5.5% |
| Both teams to score — yes @2.00-3.00 | 382 | 48.4% | 42.2% | +6.3% | +5.8% |
| Away to win @1.20-1.40 | 120 | 80.0% | 70.7% | +9.3% | +7.4% |

# BOTH SIDES STUDY — BASKETBALL: every side of every market, bet on or not

Written by `backtest/both_sides_study.py` (see its docstring). Every side of every market on every graded game is a yes/no record: SportyBet's margin-free chance vs what happened. Corrections are learned walk-forward — each day is judged only on what was learned BEFORE it.

938 graded basketball games, 5450 yes/no records, 17 match days; 16 day(s) tested on what the days before them taught.

## Does learning improve the chances?

| | Brier score (lower is better) |
|---|---|
| SportyBet's chances, margin removed | 0.23312 |
| after learning | 0.23312 |

Over 5444 records on the tested days.

## Does learning improve the picks? (£1 a game, price 1.20–2.00, chance 50%+)

| Way of picking | picks | won | expected wins | £1 return ± 1 se |
|---|---|---|---|---|
| A likeliest outcome, plain chances | 936 | 545 (58.2%) | 559 | -9.2% ± 2.6% |
| B likeliest outcome, learned chances | 936 | 545 (58.2%) | 559 | -9.2% ± 2.6% |
| C learned chances, best value within 2 pts | 936 | 543 (58.0%) | 558 | -9.4% ± 2.6% |

C picked a different outcome from A in 136 game(s).

## What has been learned (all days, groups with 50+ records)

| outcome @ price band | records | landed | price said | gap | learned shift now |
|---|---|---|---|---|---|
| winner away @1.40-1.60 | 80 | 52.5% | 62.9% | -10.4% | +0.0% |
| winner away @1.60-2.00 | 141 | 48.2% | 52.9% | -4.6% | +0.0% |
| winner home @3.00+ | 122 | 16.4% | 20.0% | -3.6% | +0.0% |
| total under @1.60-2.00 | 846 | 46.8% | 50.0% | -3.2% | +0.0% |
| winner home @1.60-2.00 | 176 | 51.7% | 53.5% | -1.8% | +0.0% |
| winner home @1.20-1.40 | 172 | 70.9% | 72.0% | -1.1% | +0.0% |
| handicap underdog @1.60-2.00 | 936 | 50.0% | 50.1% | -0.1% | +0.0% |
| winner home @1.00-1.20 | 174 | 85.6% | 85.6% | +0.1% | +0.0% |
| handicap favourite @1.60-2.00 | 932 | 50.0% | 49.9% | +0.1% | +0.0% |
| winner away @3.00+ | 328 | 21.0% | 20.5% | +0.5% | +0.0% |
| winner home @1.40-1.60 | 116 | 63.8% | 63.0% | +0.8% | +0.0% |
| winner away @1.00-1.20 | 71 | 85.9% | 85.0% | +0.9% | +0.0% |
| winner away @1.20-1.40 | 66 | 74.2% | 71.8% | +2.5% | +0.0% |
| winner away @2.00-3.00 | 241 | 43.2% | 40.0% | +3.2% | +0.0% |
| total over @1.60-2.00 | 846 | 53.3% | 50.1% | +3.2% | +0.0% |
| winner home @2.00-3.00 | 167 | 46.7% | 39.8% | +6.9% | +0.0% |

