# BOTH SIDES STUDY — FOOTBALL: every side of every market, bet on or not

Written by `backtest/both_sides_study.py` (see its docstring). Every side of every market on every graded game is a yes/no record: SportyBet's margin-free chance vs what happened. Corrections are learned walk-forward — each day is judged only on what was learned BEFORE it.

1922 graded football games, 22359 yes/no records, 6 match days; 5 day(s) tested on what the days before them taught.

## Does learning improve the chances?

| | Brier score (lower is better) |
|---|---|
| SportyBet's chances, margin removed | 0.20922 |
| after learning | 0.20945 |

Over 22345 records on the tested days.

## Does learning improve the picks? (£1 a game, price 1.20–2.00, chance 50%+)

| Way of picking | picks | won | expected wins | £1 return ± 1 se |
|---|---|---|---|---|
| A likeliest outcome, plain chances | 1839 | 1366 (74.3%) | 1336 | -5.5% ± 1.3% |
| B likeliest outcome, learned chances | 1839 | 1363 (74.1%) | 1336 | -5.7% ± 1.3% |
| C learned chances, best value within 2 pts | 1839 | 1361 (74.0%) | 1334 | -5.5% ± 1.3% |

C picked a different outcome from A in 290 game(s).

## What has been learned (all days, groups with 50+ records)

| outcome @ price band | records | landed | price said | gap | learned shift now |
|---|---|---|---|---|---|
| Away or draw @3.00+ | 62 | 11.3% | 25.9% | -14.6% | -9.8% |
| Home or draw @1.60-2.00 | 194 | 41.2% | 52.7% | -11.5% | -9.9% |
| Under 2.5 goals @1.40-1.60 | 131 | 52.7% | 60.5% | -7.8% | +0.0% |
| Away or draw @2.00-3.00 | 271 | 33.9% | 40.4% | -6.4% | -5.8% |
| Home or draw @2.00-3.00 | 102 | 34.3% | 40.6% | -6.3% | +0.0% |
| Under 2.5 goals @3.00+ | 91 | 22.0% | 27.5% | -5.5% | +0.0% |
| Both teams to score — no @1.60-2.00 | 613 | 45.4% | 50.5% | -5.2% | -4.9% |
| Over 3.5 goals @2.00-3.00 | 754 | 33.3% | 38.1% | -4.8% | -4.7% |
| Away or draw @1.60-2.00 | 470 | 48.3% | 52.3% | -4.0% | +0.0% |
| Both teams to score — yes @1.40-1.60 | 418 | 56.7% | 60.6% | -3.9% | +0.0% |
| Both teams to score — yes @1.20-1.40 | 83 | 65.1% | 68.5% | -3.5% | +0.0% |
| Away or draw @1.40-1.60 | 484 | 58.9% | 61.9% | -3.0% | +0.0% |
| Over 1.5 goals @1.40-1.60 | 115 | 60.9% | 63.0% | -2.2% | +0.0% |
| Home to win @3.00+ | 385 | 19.7% | 21.7% | -2.0% | +0.0% |
| Away to win @3.00+ | 978 | 19.5% | 21.4% | -1.8% | +0.0% |
| Over 2.5 goals @1.40-1.60 | 358 | 60.3% | 61.8% | -1.5% | +0.0% |
| Draw @3.00+ | 1820 | 23.2% | 24.7% | -1.5% | +0.0% |
| Under 1.5 goals @3.00+ | 977 | 22.4% | 23.7% | -1.2% | +0.0% |
| Away to win @2.00-3.00 | 638 | 36.7% | 37.1% | -0.4% | +0.0% |
| Over 2.5 goals @1.60-2.00 | 680 | 52.2% | 52.3% | -0.1% | +0.0% |
| Both teams to score — yes @2.00-3.00 | 170 | 42.4% | 42.5% | -0.1% | +0.0% |
| Home or draw @1.40-1.60 | 360 | 62.5% | 62.4% | +0.1% | +0.0% |
| Under 2.5 goals @2.00-3.00 | 675 | 40.6% | 40.3% | +0.3% | +0.0% |
| Over 3.5 goals @3.00+ | 535 | 26.4% | 26.1% | +0.3% | +0.0% |
| Over 2.5 goals @2.00-3.00 | 360 | 42.8% | 42.3% | +0.5% | +0.0% |
| Under 3.5 goals @1.20-1.40 | 604 | 72.2% | 71.7% | +0.5% | +0.0% |
| Over 1.5 goals @1.20-1.40 | 751 | 73.0% | 72.4% | +0.5% | +0.0% |
| Under 3.5 goals @1.00-1.20 | 71 | 80.3% | 79.7% | +0.6% | +0.0% |
| Under 1.5 goals @2.00-3.00 | 272 | 35.7% | 34.8% | +0.9% | +0.0% |
| Away to win @1.40-1.60 | 71 | 62.0% | 60.9% | +1.1% | +0.0% |
| Home to win @1.20-1.40 | 99 | 71.7% | 70.6% | +1.1% | +0.0% |
| Over 3.5 goals @1.60-2.00 | 140 | 52.1% | 50.7% | +1.4% | +0.0% |
| Over 1.5 goals @1.00-1.20 | 372 | 82.3% | 80.8% | +1.4% | +0.0% |
| Home to win @2.00-3.00 | 769 | 40.2% | 38.6% | +1.6% | +0.0% |
| Both teams to score — yes @1.60-2.00 | 756 | 53.7% | 52.0% | +1.7% | +0.0% |
| Draw @2.00-3.00 | 86 | 33.7% | 31.8% | +1.9% | +0.0% |
| Home or Away @1.20-1.40 | 1435 | 74.6% | 72.7% | +1.9% | +0.0% |
| Under 3.5 goals @2.00-3.00 | 60 | 43.3% | 41.4% | +1.9% | +0.0% |
| Away or draw @1.20-1.40 | 326 | 73.0% | 70.9% | +2.1% | +0.0% |
| Under 2.5 goals @1.60-2.00 | 618 | 54.2% | 52.0% | +2.2% | +0.0% |
| Home or draw @1.00-1.20 | 423 | 84.9% | 82.0% | +2.9% | +0.0% |
| Home or draw @1.20-1.40 | 660 | 74.7% | 71.4% | +3.3% | +0.0% |
| Home to win @1.60-2.00 | 430 | 54.9% | 51.5% | +3.4% | +0.0% |
| Both teams to score — no @1.40-1.60 | 82 | 63.4% | 59.8% | +3.6% | +0.0% |
| Under 3.5 goals @1.60-2.00 | 289 | 58.1% | 54.0% | +4.1% | +0.0% |
| Home to win @1.40-1.60 | 185 | 65.4% | 61.0% | +4.4% | +0.0% |
| Under 3.5 goals @1.40-1.60 | 433 | 67.0% | 62.5% | +4.5% | +0.0% |
| Home or Away @1.00-1.20 | 322 | 85.4% | 80.8% | +4.6% | +4.2% |
| Both teams to score — no @2.00-3.00 | 695 | 45.3% | 40.5% | +4.8% | +4.6% |
| Away to win @1.60-2.00 | 164 | 57.3% | 51.2% | +6.1% | +0.0% |
| Over 2.5 goals @1.20-1.40 | 124 | 76.6% | 70.5% | +6.1% | +0.0% |
| Away or draw @1.00-1.20 | 150 | 88.7% | 82.1% | +6.6% | +5.5% |

# BOTH SIDES STUDY — BASKETBALL: every side of every market, bet on or not

Written by `backtest/both_sides_study.py` (see its docstring). Every side of every market on every graded game is a yes/no record: SportyBet's margin-free chance vs what happened. Corrections are learned walk-forward — each day is judged only on what was learned BEFORE it.

336 graded basketball games, 1946 yes/no records, 6 match days; 5 day(s) tested on what the days before them taught.

## Does learning improve the chances?

| | Brier score (lower is better) |
|---|---|
| SportyBet's chances, margin removed | 0.23254 |
| after learning | 0.23254 |

Over 1940 records on the tested days.

## Does learning improve the picks? (£1 a game, price 1.20–2.00, chance 50%+)

| Way of picking | picks | won | expected wins | £1 return ± 1 se |
|---|---|---|---|---|
| A likeliest outcome, plain chances | 335 | 193 (57.6%) | 199 | -9.4% ± 4.3% |
| B likeliest outcome, learned chances | 335 | 193 (57.6%) | 199 | -9.4% ± 4.3% |
| C learned chances, best value within 2 pts | 335 | 193 (57.6%) | 198 | -9.2% ± 4.4% |

C picked a different outcome from A in 49 game(s).

## What has been learned (all days, groups with 50+ records)

| outcome @ price band | records | landed | price said | gap | learned shift now |
|---|---|---|---|---|---|
| winner home @1.60-2.00 | 70 | 47.1% | 53.8% | -6.7% | +0.0% |
| winner home @1.20-1.40 | 56 | 67.9% | 72.2% | -4.3% | +0.0% |
| total under @1.60-2.00 | 309 | 47.2% | 50.0% | -2.7% | +0.0% |
| handicap underdog @1.60-2.00 | 330 | 48.8% | 50.1% | -1.3% | +0.0% |
| winner away @1.60-2.00 | 50 | 52.0% | 52.5% | -0.5% | +0.0% |
| winner away @3.00+ | 109 | 21.1% | 20.3% | +0.8% | +0.0% |
| winner home @1.00-1.20 | 59 | 86.4% | 85.5% | +0.9% | +0.0% |
| handicap favourite @1.60-2.00 | 329 | 51.4% | 49.9% | +1.5% | +0.0% |
| winner away @2.00-3.00 | 96 | 42.7% | 40.3% | +2.4% | +0.0% |
| total over @1.60-2.00 | 310 | 52.9% | 50.1% | +2.8% | +0.0% |
| winner home @2.00-3.00 | 63 | 47.6% | 40.4% | +7.3% | +0.0% |

