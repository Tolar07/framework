# BOTH SIDES STUDY — FOOTBALL: every side of every market, bet on or not

Written by `backtest/both_sides_study.py` (see its docstring). Every side of every market on every graded game is a yes/no record: SportyBet's margin-free chance vs what happened. Corrections are learned walk-forward — each day is judged only on what was learned BEFORE it.

5716 graded football games, 84706 yes/no records, 19 match days; 18 day(s) tested on what the days before them taught.

## Does learning improve the chances?

| | Brier score (lower is better) |
|---|---|
| SportyBet's chances, margin removed | 0.19844 |
| after learning | 0.19831 |

Over 84692 records on the tested days.

## Does learning improve the picks? (£1 a game, price 1.20–2.00, chance 50%+)

| Way of picking | picks | won | expected wins | £1 return ± 1 se |
|---|---|---|---|---|
| A likeliest outcome, plain chances | 5428 | 4102 (75.6%) | 3947 | -4.1% ± 0.7% |
| B likeliest outcome, learned chances | 5442 | 4084 (75.0%) | 4003 | -4.4% ± 0.8% |
| C learned chances, best value within 2 pts | 5442 | 4075 (74.9%) | 3995 | -4.1% ± 0.8% |

C picked a different outcome from A in 1361 game(s).

## What has been learned (all days, groups with 50+ records)

| outcome @ price band | records | landed | price said | gap | learned shift now |
|---|---|---|---|---|---|
| Away (+0.5) Asian handicap @2.00-3.00 | 50 | 24.0% | 41.3% | -17.3% | -10.0% |
| Home (+0.5) Asian handicap @1.60-2.00 | 61 | 37.7% | 53.4% | -15.7% | -10.0% |
| Away (0:1) handicap @2.00-3.00 | 83 | 25.3% | 37.6% | -12.3% | -9.0% |
| Home or Draw & Under 2.5 @2.00-3.00 | 64 | 23.4% | 35.3% | -11.8% | +0.0% |
| Away (draw no bet) @3.00+ | 127 | 10.2% | 21.7% | -11.4% | -9.2% |
| Away or draw @3.00+ | 212 | 15.1% | 26.0% | -10.9% | -9.6% |
| Draw or Away & Under 2.5 @3.00+ | 60 | 11.7% | 22.3% | -10.7% | -7.1% |
| Draw & Under 4.5 @3.00+ | 100 | 11.0% | 21.6% | -10.6% | -8.1% |
| Home (1:0) handicap @1.60-2.00 | 56 | 41.1% | 51.6% | -10.5% | +0.0% |
| Home or draw @2.00-3.00 | 317 | 30.3% | 40.1% | -9.8% | -9.0% |
| Home (draw no bet) @2.00-3.00 | 63 | 30.2% | 39.8% | -9.6% | +0.0% |
| Home (-0.5) Asian handicap @2.00-3.00 | 96 | 31.2% | 40.8% | -9.6% | +0.0% |
| Home or draw @3.00+ | 72 | 18.1% | 26.0% | -8.0% | +0.0% |
| Draw or Away & Under 3.5 @2.00-3.00 | 50 | 28.0% | 35.8% | -7.8% | +0.0% |
| Home Clean Sheet — yes @3.00+ | 169 | 14.8% | 22.6% | -7.8% | -6.6% |
| Under 2.5 goals @3.00+ | 302 | 20.2% | 27.7% | -7.5% | -6.9% |
| Home Win to Nil — yes @3.00+ | 92 | 14.1% | 21.3% | -7.2% | +0.0% |
| Away Clean Sheet — yes @3.00+ | 254 | 13.8% | 20.9% | -7.2% | -6.4% |
| Away or draw @2.00-3.00 | 837 | 33.5% | 40.3% | -6.8% | -6.6% |
| Home & Under 4.5 @2.00-3.00 | 64 | 28.1% | 34.7% | -6.6% | +0.0% |
| Home (draw no bet) @1.60-2.00 | 71 | 45.1% | 51.7% | -6.6% | +0.0% |
| Home or draw @1.60-2.00 | 587 | 47.0% | 53.0% | -6.0% | -5.7% |
| Under 3.5 goals @2.00-3.00 | 189 | 35.4% | 41.3% | -5.9% | +0.0% |
| Home (-1.5) Asian handicap @2.00-3.00 | 57 | 35.1% | 40.7% | -5.6% | +0.0% |
| Away Under 0.5 goals @2.00-3.00 | 65 | 32.3% | 37.8% | -5.5% | +0.0% |
| Draw (0:2) handicap @3.00+ | 108 | 11.1% | 16.5% | -5.4% | +0.0% |
| Away or draw @1.60-2.00 | 1368 | 47.1% | 52.4% | -5.3% | -5.2% |
| Teams to Score: Only Home @3.00+ | 238 | 13.0% | 18.4% | -5.3% | -4.7% |
| Under 2.5 & No @2.00-3.00 | 65 | 29.2% | 34.4% | -5.2% | +0.0% |
| Draw or Away & No @3.00+ | 90 | 13.3% | 18.5% | -5.2% | +0.0% |
| Home or Draw & No @3.00+ | 58 | 15.5% | 20.7% | -5.2% | +0.0% |
| Home or Draw & Over 3.5 @3.00+ | 84 | 13.1% | 18.3% | -5.2% | +0.0% |
| Home Clean Sheet — yes @2.00-3.00 | 131 | 32.1% | 36.7% | -4.7% | +0.0% |
| Away Goals: 0 @2.00-3.00 | 113 | 31.0% | 35.6% | -4.6% | +0.0% |
| Draw & Under 2.5 @3.00+ | 121 | 13.2% | 17.7% | -4.4% | +0.0% |
| Draw & Under 3.5 @3.00+ | 120 | 13.3% | 17.6% | -4.3% | +0.0% |
| Draw & Over 1.5 @3.00+ | 122 | 13.9% | 18.2% | -4.3% | +0.0% |
| Teams to Score: Both teams @2.00-3.00 | 60 | 36.7% | 40.6% | -3.9% | +0.0% |
| Both teams to score — no @1.60-2.00 | 1635 | 46.7% | 50.5% | -3.8% | -3.7% |
| Under 2.5 goals @1.40-1.60 | 395 | 57.2% | 60.9% | -3.6% | +0.0% |
| Home or Draw & Under 1.5 @3.00+ | 119 | 12.6% | 16.2% | -3.6% | +0.0% |
| Home or Draw & No @2.00-3.00 | 51 | 31.4% | 34.9% | -3.5% | +0.0% |
| Under 2.5 & Yes @3.00+ | 122 | 8.2% | 11.7% | -3.5% | +0.0% |
| Away Win to Nil — yes @3.00+ | 112 | 14.3% | 17.8% | -3.5% | +0.0% |
| Both teams to score — no @1.40-1.60 | 230 | 56.5% | 59.9% | -3.4% | +0.0% |
| Away (draw no bet) @2.00-3.00 | 94 | 35.1% | 38.4% | -3.2% | +0.0% |
| Home (0:1) handicap @3.00+ | 181 | 17.7% | 20.9% | -3.2% | +0.0% |
| Both teams to score — no @3.00+ | 103 | 25.2% | 28.4% | -3.2% | +0.0% |
| Home or Away & Over 3.5 @3.00+ | 71 | 18.3% | 21.5% | -3.2% | +0.0% |
| Away to win @3.00+ | 2911 | 17.9% | 20.9% | -3.0% | -3.0% |
| Over 2.5 & No @3.00+ | 119 | 8.4% | 11.4% | -3.0% | +0.0% |
| Under 1.5 goals @3.00+ | 2733 | 20.4% | 23.3% | -2.9% | -2.9% |
| Draw or Away & Under 1.5 @3.00+ | 123 | 12.2% | 15.0% | -2.8% | +0.0% |
| Under 2.5 goals @2.00-3.00 | 1919 | 37.5% | 40.3% | -2.8% | -2.8% |
| Away Goals: 0 @3.00+ | 175 | 17.1% | 19.9% | -2.8% | +0.0% |
| Over 4.5 goals @3.00+ | 157 | 19.1% | 21.8% | -2.7% | +0.0% |
| Home or Away & No @2.00-3.00 | 86 | 33.7% | 36.4% | -2.7% | +0.0% |
| Odd/Even: Even @1.60-2.00 | 408 | 48.5% | 51.0% | -2.5% | +0.0% |
| Home Goals: 0 @3.00+ | 257 | 15.6% | 18.0% | -2.5% | +0.0% |
| Under 0.5 goals @3.00+ | 91 | 9.9% | 12.3% | -2.4% | +0.0% |
| Home Goals: 1 @3.00+ | 113 | 22.1% | 24.4% | -2.3% | +0.0% |
| Under 1.5 goals @2.00-3.00 | 714 | 32.9% | 35.1% | -2.2% | +0.0% |
| Away or draw @1.40-1.60 | 1316 | 59.8% | 62.0% | -2.2% | +0.0% |
| Draw & Under 1.5 @3.00+ | 122 | 4.9% | 7.0% | -2.0% | +0.0% |
| Home (0:2) handicap @3.00+ | 97 | 11.3% | 13.3% | -2.0% | +0.0% |
| Home or Away & Under 1.5 @3.00+ | 123 | 15.4% | 17.3% | -1.9% | +0.0% |
| Away & Over 4.5 @3.00+ | 121 | 5.0% | 6.7% | -1.7% | +0.0% |
| Under 3.5 goals @1.60-2.00 | 822 | 52.2% | 53.9% | -1.7% | +0.0% |
| Away Clean Sheet — no @1.20-1.40 | 113 | 69.9% | 71.5% | -1.6% | +0.0% |
| Home Goals: 1 @2.00-3.00 | 213 | 32.4% | 34.0% | -1.6% | +0.0% |
| Draw @3.00+ | 5360 | 22.8% | 24.3% | -1.5% | -1.5% |
| Under 2.5 goals @1.60-2.00 | 1582 | 50.3% | 51.7% | -1.4% | +0.0% |
| Away Goals: 1 @2.00-3.00 | 277 | 33.2% | 34.6% | -1.4% | +0.0% |
| Home Goals: 2 @3.00+ | 326 | 22.7% | 24.1% | -1.4% | +0.0% |
| Draw & Over 2.5 @3.00+ | 122 | 5.7% | 7.1% | -1.3% | +0.0% |
| Both teams to score — yes @1.20-1.40 | 248 | 67.3% | 68.6% | -1.3% | +0.0% |
| Draw & Over 3.5 @3.00+ | 122 | 5.7% | 7.0% | -1.3% | +0.0% |
| Under 3.5 goals @1.40-1.60 | 1250 | 61.3% | 62.5% | -1.2% | +0.0% |
| Home or Away & Under 2.5 @3.00+ | 70 | 22.9% | 24.0% | -1.2% | +0.0% |
| Home & Over 3.5 @3.00+ | 106 | 12.3% | 13.4% | -1.2% | +0.0% |
| Home & Under 1.5 @3.00+ | 122 | 8.2% | 9.1% | -0.9% | +0.0% |
| Away (2:0) handicap @3.00+ | 67 | 9.0% | 9.9% | -0.9% | +0.0% |
| Draw or Away & Over 4.5 @3.00+ | 120 | 7.5% | 8.4% | -0.9% | +0.0% |
| Teams to Score: None @3.00+ | 326 | 6.1% | 6.8% | -0.7% | +0.0% |
| Away & Under 4.5 @3.00+ | 78 | 17.9% | 18.6% | -0.7% | +0.0% |
| Home & Under 2.5 @3.00+ | 120 | 15.0% | 15.6% | -0.6% | +0.0% |
| Home or draw @1.40-1.60 | 1031 | 62.0% | 62.5% | -0.5% | +0.0% |
| Away Goals: 2 @3.00+ | 326 | 21.2% | 21.6% | -0.4% | +0.0% |
| Under 3.5 goals @1.00-1.20 | 226 | 79.2% | 79.6% | -0.4% | +0.0% |
| Teams to Score: Only Away @3.00+ | 299 | 14.0% | 14.4% | -0.4% | +0.0% |
| Both teams to score — yes @1.40-1.60 | 1130 | 60.4% | 60.8% | -0.4% | +0.0% |
| Home Under 1.5 goals @1.60-2.00 | 66 | 51.5% | 51.9% | -0.4% | +0.0% |
| Home or Away & Over 4.5 @3.00+ | 111 | 16.2% | 16.6% | -0.4% | +0.0% |
| Home or Away & Under 4.5 @1.40-1.60 | 71 | 57.7% | 58.1% | -0.3% | +0.0% |
| Both teams to score — no @2.00-3.00 | 1977 | 40.3% | 40.5% | -0.2% | +0.0% |
| Under 3.5 goals @1.20-1.40 | 1514 | 71.3% | 71.5% | -0.2% | +0.0% |
| Away & Under 1.5 @3.00+ | 122 | 7.4% | 7.5% | -0.1% | +0.0% |
| Home or Draw & Yes @2.00-3.00 | 71 | 36.6% | 36.8% | -0.1% | +0.0% |
| Draw or Away & Over 3.5 @3.00+ | 108 | 15.7% | 15.7% | +0.0% | +0.0% |
| Away & Under 2.5 @3.00+ | 122 | 12.3% | 12.2% | +0.0% | +0.0% |
| Home to win @3.00+ | 1204 | 21.9% | 21.8% | +0.1% | +0.0% |
| Home or Away & Under 2.5 @2.00-3.00 | 53 | 34.0% | 33.8% | +0.2% | +0.0% |
| Over 3.5 goals @3.00+ | 1355 | 26.2% | 26.0% | +0.2% | +0.0% |
| Draw (2:0) handicap @3.00+ | 75 | 14.7% | 14.4% | +0.2% | +0.0% |
| Over 3.5 goals @2.00-3.00 | 2129 | 38.4% | 38.1% | +0.3% | +0.0% |
| Away Under 1.5 goals @1.60-2.00 | 61 | 52.5% | 52.0% | +0.5% | +0.0% |
| Over 2.5 goals @2.00-3.00 | 941 | 42.3% | 41.8% | +0.5% | +0.0% |
| Away & Over 3.5 @3.00+ | 117 | 10.3% | 9.7% | +0.5% | +0.0% |
| Away to win @2.00-3.00 | 1828 | 37.9% | 37.2% | +0.7% | +0.0% |
| Home to win @2.00-3.00 | 2151 | 39.4% | 38.7% | +0.8% | +0.0% |
| Home or Draw & Over 4.5 @3.00+ | 118 | 12.7% | 11.9% | +0.8% | +0.0% |
| Draw & Over 4.5 @3.00+ | 122 | 2.5% | 1.6% | +0.9% | +0.0% |
| Over 2.5 goals @1.40-1.60 | 1024 | 62.8% | 61.8% | +1.0% | +0.0% |
| Over 5.5 goals @3.00+ | 62 | 17.7% | 16.6% | +1.1% | +0.0% |
| Home & Over 4.5 @3.00+ | 119 | 10.9% | 9.7% | +1.3% | +0.0% |
| Under 4.5 goals @1.20-1.40 | 102 | 74.5% | 72.9% | +1.6% | +0.0% |
| Home or Away @1.20-1.40 | 4139 | 74.4% | 72.8% | +1.6% | +1.6% |
| Draw or Away & Under 2.5 @2.00-3.00 | 54 | 37.0% | 35.3% | +1.8% | +0.0% |
| Away (0:1) handicap @1.60-2.00 | 103 | 52.4% | 50.6% | +1.9% | +0.0% |
| Away & Under 3.5 @3.00+ | 100 | 20.0% | 18.1% | +1.9% | +0.0% |
| Away (+0.5) Asian handicap @1.60-2.00 | 109 | 54.1% | 52.2% | +2.0% | +0.0% |
| Away or draw @1.20-1.40 | 999 | 72.9% | 70.9% | +2.0% | +0.0% |
| Home Goals: 3+ @3.00+ | 235 | 19.1% | 17.1% | +2.0% | +0.0% |
| Teams to Score: Only Home @2.00-3.00 | 78 | 37.2% | 35.1% | +2.1% | +0.0% |
| Home or draw @1.20-1.40 | 1881 | 73.7% | 71.6% | +2.2% | +2.1% |
| Away & Over 2.5 @3.00+ | 98 | 17.3% | 15.1% | +2.2% | +0.0% |
| Home & Under 3.5 @3.00+ | 68 | 23.5% | 21.2% | +2.3% | +0.0% |
| Over 1.5 goals @1.00-1.20 | 1121 | 83.3% | 81.0% | +2.4% | +2.3% |
| Over 0.5 goals @1.00-1.20 | 91 | 90.1% | 87.7% | +2.4% | +0.0% |
| Odd/Even: Odd @1.60-2.00 | 406 | 51.5% | 49.0% | +2.5% | +0.0% |
| Away to win @1.00-1.20 | 54 | 85.2% | 82.6% | +2.6% | +0.0% |
| Home Over 1.5 goals @1.60-2.00 | 65 | 53.8% | 51.3% | +2.6% | +0.0% |
| Draw (1:0) handicap @3.00+ | 202 | 22.8% | 20.2% | +2.6% | +0.0% |
| Away to win @1.60-2.00 | 505 | 53.7% | 51.1% | +2.6% | +0.0% |
| Over 1.5 goals @1.20-1.40 | 1941 | 75.4% | 72.7% | +2.7% | +2.7% |
| Over 2.5 & Yes @2.00-3.00 | 56 | 39.3% | 36.5% | +2.8% | +0.0% |
| Draw (0:1) handicap @3.00+ | 286 | 25.2% | 22.3% | +2.9% | +0.0% |
| Home (0:1) handicap @2.00-3.00 | 90 | 40.0% | 37.1% | +2.9% | +0.0% |
| Both teams to score — yes @1.60-2.00 | 2109 | 55.2% | 52.1% | +3.1% | +3.0% |
| Away or draw @1.00-1.20 | 439 | 85.6% | 82.5% | +3.2% | +0.0% |
| Draw or Away & Yes @2.00-3.00 | 74 | 39.2% | 35.9% | +3.3% | +0.0% |
| Home to win @1.00-1.20 | 136 | 85.3% | 81.8% | +3.5% | +0.0% |
| Away Win to Nil — no @1.00-1.20 | 90 | 87.8% | 84.2% | +3.5% | +0.0% |
| Home to win @1.60-2.00 | 1257 | 55.1% | 51.5% | +3.6% | +3.5% |
| Away Clean Sheet — yes @2.00-3.00 | 80 | 40.0% | 36.4% | +3.6% | +0.0% |
| Under 4.5 goals @1.00-1.20 | 67 | 88.1% | 84.3% | +3.8% | +0.0% |
| Draw or Away & Over 1.5 @2.00-3.00 | 51 | 41.2% | 37.4% | +3.8% | +0.0% |
| Over 2.5 goals @1.60-2.00 | 1849 | 56.3% | 52.5% | +3.8% | +3.8% |
| Draw @2.00-3.00 | 277 | 36.1% | 32.0% | +4.1% | +0.0% |
| Home to win @1.20-1.40 | 353 | 74.8% | 70.7% | +4.1% | +0.0% |
| Under 2.5 goals @1.20-1.40 | 55 | 72.7% | 68.6% | +4.1% | +0.0% |
| Draw or Away & Over 2.5 @3.00+ | 77 | 23.4% | 19.2% | +4.2% | +0.0% |
| Home Over 1.5 goals @2.00-3.00 | 66 | 43.9% | 39.7% | +4.3% | +0.0% |
| Away Goals: 3+ @3.00+ | 288 | 17.7% | 13.4% | +4.3% | +3.9% |
| Both teams to score — yes @2.00-3.00 | 463 | 46.4% | 42.1% | +4.3% | +0.0% |
| Home Goals: 3+ @2.00-3.00 | 68 | 39.7% | 35.1% | +4.6% | +0.0% |
| Away & Over 1.5 @3.00+ | 86 | 22.1% | 17.5% | +4.6% | +0.0% |
| Home & Over 2.5 @3.00+ | 69 | 23.2% | 18.4% | +4.8% | +0.0% |
| Away (+0.5) Asian handicap @1.40-1.60 | 59 | 66.1% | 61.3% | +4.8% | +0.0% |
| Home to win @1.40-1.60 | 536 | 66.0% | 61.2% | +4.9% | +4.6% |
| Over 1.5 goals @1.40-1.60 | 350 | 68.0% | 63.1% | +4.9% | +0.0% |
| Away (1:0) handicap @3.00+ | 164 | 22.0% | 17.0% | +4.9% | +0.0% |
| Home Goals: 0 @2.00-3.00 | 64 | 40.6% | 35.5% | +5.1% | +0.0% |
| Home or Away @1.00-1.20 | 1003 | 86.1% | 81.0% | +5.2% | +5.0% |
| Away (0:1) handicap @1.40-1.60 | 62 | 64.5% | 59.3% | +5.2% | +0.0% |
| Home or draw @1.00-1.20 | 1284 | 87.6% | 82.3% | +5.3% | +5.2% |
| Away to win @1.40-1.60 | 198 | 66.7% | 61.2% | +5.4% | +0.0% |
| Home Clean Sheet — no @1.40-1.60 | 79 | 67.1% | 61.6% | +5.5% | +0.0% |
| Home (draw no bet) @1.40-1.60 | 61 | 67.2% | 61.6% | +5.6% | +0.0% |
| Teams to Score: Both teams @1.40-1.60 | 99 | 65.7% | 59.4% | +6.3% | +0.0% |
| Over 3.5 goals @1.60-2.00 | 422 | 57.3% | 50.7% | +6.6% | +6.2% |
| Home Clean Sheet — no @1.20-1.40 | 119 | 77.3% | 70.6% | +6.7% | +0.0% |
| Over 2.5 goals @1.20-1.40 | 402 | 77.4% | 70.5% | +6.9% | +6.4% |
| Away Over 0.5 goals @1.40-1.60 | 52 | 69.2% | 62.2% | +7.1% | +0.0% |
| Away (draw no bet) @1.60-2.00 | 73 | 58.9% | 51.2% | +7.7% | +0.0% |
| Home Win to Nil — no @1.00-1.20 | 53 | 90.6% | 82.5% | +8.1% | +0.0% |
| Home or Away & Under 3.5 @1.60-2.00 | 78 | 56.4% | 48.2% | +8.2% | +0.0% |
| Home Clean Sheet — no @1.00-1.20 | 96 | 89.6% | 80.9% | +8.6% | +6.6% |
| Over 3.5 goals @1.40-1.60 | 87 | 70.1% | 61.5% | +8.6% | +0.0% |
| Home (-0.5) Asian handicap @1.60-2.00 | 91 | 59.3% | 50.7% | +8.6% | +0.0% |
| Home or Away & Yes @2.00-3.00 | 79 | 45.6% | 36.8% | +8.8% | +0.0% |
| Away Over 1.5 goals @2.00-3.00 | 75 | 48.0% | 39.1% | +8.9% | +0.0% |
| Away Clean Sheet — no @1.00-1.20 | 174 | 90.8% | 81.8% | +9.0% | +7.7% |
| Away to win @1.20-1.40 | 141 | 80.1% | 70.6% | +9.6% | +7.9% |
| Home (draw no bet) @1.20-1.40 | 72 | 81.9% | 71.5% | +10.4% | +0.0% |
| Teams to Score: Both teams @1.60-2.00 | 122 | 61.5% | 50.3% | +11.1% | +8.9% |
| Away (-0.5) Asian handicap @2.00-3.00 | 81 | 51.9% | 40.3% | +11.5% | +8.4% |
| Home or Away & Over 2.5 @1.60-2.00 | 53 | 60.4% | 48.6% | +11.8% | +0.0% |
| Home (draw no bet) @1.00-1.20 | 72 | 94.4% | 82.6% | +11.9% | +8.4% |

# BOTH SIDES STUDY — BASKETBALL: every side of every market, bet on or not

Written by `backtest/both_sides_study.py` (see its docstring). Every side of every market on every graded game is a yes/no record: SportyBet's margin-free chance vs what happened. Corrections are learned walk-forward — each day is judged only on what was learned BEFORE it.

1167 graded basketball games, 10488 yes/no records, 19 match days; 18 day(s) tested on what the days before them taught.

## Does learning improve the chances?

| | Brier score (lower is better) |
|---|---|
| SportyBet's chances, margin removed | 0.22955 |
| after learning | 0.22943 |

Over 10482 records on the tested days.

## Does learning improve the picks? (£1 a game, price 1.20–2.00, chance 50%+)

| Way of picking | picks | won | expected wins | £1 return ± 1 se |
|---|---|---|---|---|
| A likeliest outcome, plain chances | 1165 | 695 (59.7%) | 703 | -8.1% ± 2.3% |
| B likeliest outcome, learned chances | 1165 | 695 (59.7%) | 703 | -8.1% ± 2.3% |
| C learned chances, best value within 2 pts | 1165 | 694 (59.6%) | 702 | -8.0% ± 2.3% |

C picked a different outcome from A in 186 game(s).

## What has been learned (all days, groups with 50+ records)

| outcome @ price band | records | landed | price said | gap | learned shift now |
|---|---|---|---|---|---|
| total under @3.00+ | 105 | 12.4% | 26.8% | -14.4% | -10.0% |
| handicap favourite @2.00-3.00 | 296 | 28.7% | 41.2% | -12.5% | -10.0% |
| handicap favourite @3.00+ | 87 | 12.6% | 24.2% | -11.5% | -8.6% |
| winner away @1.40-1.60 | 96 | 52.1% | 62.7% | -10.6% | -8.1% |
| total under @1.20-1.40 | 108 | 65.7% | 71.9% | -6.1% | +0.0% |
| handicap favourite @1.40-1.60 | 51 | 58.8% | 63.2% | -4.4% | +0.0% |
| winner home @3.00+ | 160 | 16.2% | 20.0% | -3.8% | +0.0% |
| winner away @1.60-2.00 | 178 | 49.4% | 53.0% | -3.5% | +0.0% |
| handicap favourite @1.60-2.00 | 1356 | 48.2% | 50.4% | -2.1% | +0.0% |
| total over @2.00-3.00 | 384 | 39.3% | 41.4% | -2.1% | +0.0% |
| winner home @1.60-2.00 | 218 | 51.8% | 53.4% | -1.5% | +0.0% |
| total under @2.00-3.00 | 379 | 40.1% | 41.4% | -1.3% | +0.0% |
| winner away @3.00+ | 406 | 19.5% | 20.2% | -0.8% | +0.0% |
| winner home @1.40-1.60 | 141 | 62.4% | 63.1% | -0.6% | +0.0% |
| total under @1.60-2.00 | 1546 | 50.5% | 50.8% | -0.3% | +0.0% |
| winner home @1.00-1.20 | 220 | 85.9% | 85.7% | +0.2% | +0.0% |
| total over @1.60-2.00 | 1539 | 51.2% | 50.8% | +0.4% | +0.0% |
| total under @1.40-1.60 | 147 | 63.3% | 62.6% | +0.7% | +0.0% |
| winner away @1.00-1.20 | 92 | 85.9% | 85.1% | +0.8% | +0.0% |
| winner home @1.20-1.40 | 212 | 73.1% | 72.1% | +1.0% | +0.0% |
| winner away @1.20-1.40 | 87 | 73.6% | 71.8% | +1.8% | +0.0% |
| handicap underdog @1.60-2.00 | 1406 | 53.6% | 50.8% | +2.8% | +2.8% |
| winner away @2.00-3.00 | 297 | 43.8% | 39.8% | +4.0% | +0.0% |
| winner home @2.00-3.00 | 205 | 46.3% | 39.9% | +6.5% | +0.0% |
| total over @3.00+ | 94 | 34.0% | 27.5% | +6.5% | +0.0% |
| total over @1.40-1.60 | 150 | 69.3% | 62.5% | +6.8% | +0.0% |
| handicap underdog @2.00-3.00 | 172 | 49.4% | 42.5% | +6.9% | +0.0% |
| total over @1.20-1.40 | 117 | 85.5% | 72.6% | +12.9% | +10.0% |
| handicap underdog @1.40-1.60 | 124 | 76.6% | 63.0% | +13.6% | +10.0% |
| handicap underdog @1.20-1.40 | 68 | 92.6% | 73.8% | +18.8% | +10.0% |

