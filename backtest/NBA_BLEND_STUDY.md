# NBA BLEND STUDY — model vs SportyBet's own price, per market group

p = w × sharp-line model + (1 − w) × SportyBet fair (margin removed). w learned on games before 2026-10-28, judged on the games from then on. Log loss: lower is better (model only / blend / SportyBet only). Picks: the board's bars with that chance, one per game and group, on the later games. Written by `backtest/nba_blend_study.py`.

| Group | w used | w fitted | outcomes learn / test | log loss model · blend · SportyBet | picks, model only | picks, blend | |
|---|---:|---:|---|---|---|---|---|
| 1st half handicap | 0.00 | 0.00 | 1228 / 1474 | 0.6699 · 0.6671 · 0.6671 | 2 · +0.0% ± 100.0% | — | blend beats the model on the later half |
| 1st half total | 1.00 | 0.35 | 1228 / 1474 | 0.6584 · 0.6657 · 0.6768 | 64 · +9.4% ± 12.2% | 1 · +100.0% | model alone holds |
| 1st quarter total | 1.00 | — | — | — | — | — | too few outcomes (112 / 134) |
| 2nd half | 0.50 | 0.50 | 2332 / 2772 | 0.7105 · 0.6907 · 0.6764 | 59 · -24.4% ± 12.4% | 11 · -47.0% ± 27.4% | blend beats the model on the later half |
| handicap | 0.00 | 0.00 | 2918 / 3492 | 0.6081 · 0.6015 · 0.6015 | 4 · -55.2% ± 44.8% | — | blend beats the model on the later half |
| quarter handicap | 1.00 | 0.00 | 2240 / 2680 | 0.6866 · 0.6876 · 0.6876 | 5 · +15.0% ± 47.0% | — | model alone holds |
| quarter total Q2-Q4 | 0.00 | 0.00 | 304 / 360 | 0.7022 · 0.6938 · 0.6938 | 116 · -0.3% ± 8.8% | — | blend beats the model on the later half |
| team period points | 1.00 | 0.50 | 2240 / 2680 | 0.6737 · 0.6762 · 0.6834 | 175 · +4.6% ± 7.3% | 16 · +22.0% ± 24.4% | model alone holds |
| team total | 1.00 | 1.00 | 1120 / 1340 | 0.6928 · 0.6928 · 0.6885 | — | — | model alone holds |
| total | 1.00 | 1.00 | 3136 / 3752 | 0.6333 · 0.6333 · 0.6324 | — | — | model alone holds |
| winner | 1.00 | — | — | — | — | — | too few outcomes (112 / 134) |
