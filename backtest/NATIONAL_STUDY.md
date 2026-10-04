# NATIONAL-TEAM STUDY — new national Elo vs the old model

Test: 450 competitive UEFA internationals since 2024-01-01 (Nations League, Euro + World Cup qualifiers, Euro finals); neither model saw a match before predicting it. Lower is better.

| Model | 1X2 Brier | 1X2 log loss | Over 2.5 Brier | 'no draw' Brier |
|---|---|---|---|---|
| national Elo (new) | 0.4712 | 0.8035 | 0.2477 | 0.1613 |
| UEFA Dixon-Coles (old) | 0.4779 | 0.8199 | 0.2341 | 0.1637 |
| blend (average) | 0.4703 | 0.8062 | 0.2352 | 0.1617 |

Best on log loss: **national Elo (new)**.

