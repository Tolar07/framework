# BIAS CHECKS STUDY — 2026-10-27T21:04Z

To-do #7 idea 2, RECORDED ONLY. Walk-forward: each day's sides are read against the (market, price band) table of games BEFORE that day. Later half: 2026-10-17 .. 2026-10-27, 81064 sides. Lean = |shrunk bias| > 1%.

## Every side, by the lean of its cell

| set | n | landed | return |
|---|---|---|---|
| all | 81064 | 42.6% | -11.9% ± 0.5% ** |
| cell says too long (shrunk > +1%) | 20252 | 65.8% | -5.2% ± 0.5% ** |
| no lean | 34974 | 40.2% | -13.1% ± 0.8% ** |
| cell says too short (shrunk < -1%) | 25838 | 27.7% | -15.7% ± 1.1% ** |

## Same split inside each price band (the control)

| band | all | too long | too short |
|---|---|---|---|
| 1.01-1.20 | 4707 / 85.9% / -3.7% ± 0.6% ** | 4054 / 86.0% / -3.5% ± 0.6% ** | 0 |
| 1.20-1.30 | 5768 / 76.5% / -4.6% ± 0.7% ** | 5282 / 76.5% / -4.7% ± 0.7% ** | 1 / 100.0% / +29.0% ± 0.0% ** |
| 1.30-1.50 | 7965 / 67.2% / -6.8% ± 0.7% ** | 1895 / 67.1% / -6.5% ± 1.5% ** | 559 / 62.8% / -10.9% ± 2.9% ** |
| 1.50-1.75 | 9121 / 57.9% / -6.6% ± 0.8% ** | 4423 / 58.8% / -5.2% ± 1.2% ** | 1690 / 54.3% / -12.9% ± 1.9% ** |
| 1.75-2.00 | 8716 / 49.0% / -9.0% ± 1.0% ** | 1141 / 48.6% / -9.1% ± 2.8% ** | 943 / 46.7% / -13.6% ± 3.0% ** |
| 2.00-2.50 | 10074 / 40.1% / -11.1% ± 1.1% ** | 2735 / 42.6% / -5.4% ± 2.1% ** | 4136 / 39.7% / -12.8% ± 1.7% ** |
| 2.50-4.00 | 17859 / 28.1% / -12.7% ± 1.1% ** | 722 / 29.1% / -8.0% ± 5.4% | 9058 / 28.2% / -12.4% ± 1.5% ** |
| 4.00+ | 16854 / 12.7% / -23.3% ± 1.9% ** | 0 | 9451 / 13.4% / -21.1% ± 2.6% ** |

## Board singles, as of their board date (later half)

| set | n | landed | return |
|---|---|---|---|
| all | 516 | 75.0% | -5.7% ± 2.4% ** |
| pick's cell too long (> +1%) | 403 | 74.7% | -7.4% ± 2.7% ** |
| pick's cell too short (< -1%) | 0 | | |
| other side's cell too long (> +1%) | 0 | | |
| short leg (< 1.30) | 416 | 75.2% | -6.8% ± 2.6% ** |
| 1.30 and over | 100 | 74.0% | -1.2% ± 5.9% |

** = return more than 2 standard errors from zero. Nothing here changes a stake; wiring this into picks or stakes needs the Architect's OK after out-of-sample gains.
