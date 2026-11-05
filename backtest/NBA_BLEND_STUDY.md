# NBA BLEND STUDY — model vs SportyBet's own price, per market group

p = w × sharp-line model + (1 − w) × SportyBet fair (margin removed). w learned on games before 2026-10-28, judged on the games from then on. Log loss: lower is better (model only / blend / SportyBet only). Picks: the board's bars with that chance, one per game and group, on the later games. Written by `backtest/nba_blend_study.py`.

| Group | w used | w fitted | outcomes learn / test | log loss model · blend · SportyBet | picks, model only | picks, blend | |
|---|---:|---:|---|---|---|---|---|
| 1st half handicap | 0.00 | 0.00 | 1206 / 1452 | 0.6708 · 0.6679 · 0.6679 | 2 · +0.0% ± 100.0% | — | blend beats the model on the later half |
| 1st half total | 1.00 | 0.45 | 1206 / 1452 | 0.6671 · 0.6684 · 0.6788 | 63 · +4.9% ± 12.3% | 22 · +24.0% ± 20.5% | model alone holds |
| 1st quarter total | 1.00 | — | — | — | — | — | too few outcomes (110 / 132) |
| 2nd half | 0.40 | 0.40 | 2288 / 2728 | 0.7130 · 0.6906 · 0.6801 | 58 · -22.9% ± 12.6% | 1 · -100.0% | blend beats the model on the later half |
| handicap | 0.00 | 0.00 | 2866 / 3440 | 0.6031 · 0.5960 · 0.5960 | 4 · -55.2% ± 44.8% | — | blend beats the model on the later half |
| quarter handicap | 1.00 | 0.00 | 2200 / 2640 | 0.6862 · 0.6869 · 0.6869 | 5 · +15.0% ± 47.0% | — | model alone holds |
| quarter total Q2-Q4 | 0.00 | 0.00 | 298 / 356 | 0.7035 · 0.6940 · 0.6940 | 116 · -1.8% ± 8.9% | — | blend beats the model on the later half |
| team period points | 0.65 | 0.65 | 2200 / 2640 | 0.6780 · 0.6778 · 0.6836 | 171 · +0.3% ± 7.4% | 75 · +16.6% ± 11.1% | blend beats the model on the later half |
| team total | 0.70 | 0.70 | 1100 / 1320 | 0.6942 · 0.6927 · 0.6895 | — | — | blend beats the model on the later half |
| total | 1.00 | 1.00 | 3080 / 3696 | 0.6359 · 0.6359 · 0.6348 | — | — | model alone holds |
| winner | 1.00 | — | — | — | — | — | too few outcomes (110 / 132) |
