# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

7679 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 890 | 73% | -1.2% ± 2.0% | -0.0% | £89.24 | +2.3% / -1.7% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 2461 | 56% | -3.6% ± 1.7% | -0.2% | £10.42 | -1.8% / -3.9% | losing — avoid |
| F3 home underdog | home win at 2.50–5.00 | 1839 | 29% | -10.4% ± 3.3% | -0.7% | £-92.14 | -9.4% / -10.6% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 1275 | 27% | -12.6% ± 4.1% | -0.3% | £-60.55 | -25.8% / -10.7% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 3034 | 63% | -2.3% ± 1.4% | -0.1% | £29.32 | -2.1% / -2.4% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 1688 | 56% | -8.5% ± 2.0% | -0.9% | £-43.13 | -8.3% / -8.5% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 2003 | 48% | -15.2% ± 2.0% | -0.4% | £-204.53 | -19.2% / -14.8% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 3787 | 75% | -4.6% ± 0.9% | -0.3% | £-74.89 | +1.7% / -5.6% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 4553 | 74% | -6.0% ± 0.8% | -0.1% | £-174.19 | -0.8% / -6.8% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 2908 | 49% | -3.1% ± 1.9% | -0.4% | £9.45 | +7.1% / -4.5% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 33 | 88% | +2.8% ± 6.8% | -2.3% | £100.93 | -11.3% / +7.3% | learning (33/100 bets) |
| F12 strong home, plain | home win on F11's games | 33 | 85% | +0.3% ± 7.5% | -2.2% | £100.10 | -10.4% / +3.7% | learning (33/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 33 | 94% | -1.8% ± 4.4% | -0.9% | £99.41 | -21.4% / +4.5% | learning (33/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 246 | 57% | -6.6% ± 5.2% | +1.6% | £83.82 | -9.3% / +0.5% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 246 | 58% | -4.7% ± 5.3% | +1.0% | £88.47 | -7.9% / +3.6% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 16 | 81% | +0.4% ± 12.6% | +1.5% | £100.07 | +30.4% / -13.2% | learning (16/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 9 | 44% | -22.1% ± 30.9% | +2.1% | £98.01 | +72.0% / -49.0% | learning (9/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 137 | 67% | -7.3% ± 5.6% | -3.2% | £90.06 | -3.8% / -13.5% | no edge shown |
| B1 home favourite | home winner at 1.20–1.60 | 383 | 69% | -5.5% ± 3.3% | -0.0% | £79.00 | +4.1% / -6.3% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 432 | 39% | -3.3% ± 6.0% | -0.8% | £85.67 | +12.4% / -4.8% | no edge shown |
| B3 main total under | Under the main total line | 1116 | 48% | -11.1% ± 2.8% | -0.2% | £-23.94 | -7.4% / -11.4% | losing — avoid |
| B4 main total over | Over the main total line | 1116 | 52% | -3.6% ± 2.8% | +0.0% | £59.73 | -4.8% / -3.5% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 241: 137 draw(s), 104 beaten |
| F2 mid favourite | lost 1092: 576 draw(s), 516 beaten |
| F3 home underdog | lost 1306: 484 draw(s), 822 beaten |
| F4 draw, tight game | lost 934; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 1048; goals in those games avg 3.7 |
| F8 safe double chance | lost 930; goals in those games avg 2.5 |
| F9 draw-proof | lost 1177; goals in those games avg 2.2 |
| F10 mid-price home | lost 1492: 765 draw(s), 727 beaten |
| F11 2UP strong home | won 29 (1 only by the early payout), lost 4 |
| F12 strong home, plain | lost 5: 3 draw(s), 2 beaten |
| F13 strong home, double chance | lost 2; goals in those games avg 4.0 |
| P1 profile: BTTS yes | lost 105; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +1.9, losses -1.1 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.6, losses +1.2 |
| P4 profile: BTTS no | lost 5; goals in those games avg 4.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.6, losses +1.4 |
| B1 home favourite | lost 118 by 8 pts on average |
| B2 away underdog | lost 264 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -13.1, losses +14.7 |
| B4 main total over | total vs line (pts): wins +14.7, losses -13.1 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 20 | 10/20 | -10.6% | 50% vs 46% | 48/60 |
| A2 three favourites | 3 legs from F1 + F2 | 20 | 10/20 | +3.6% | 50% vs 42% | 49/60 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 20 | 7/20 | -37.0% | 35% vs 47% | 45/60 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 18 | 9/18 | -11.3% | 50% vs 47% | 43/54 |

Latest accas (2026-10-26):
- A1 three safe double chances @2.03 — LANDED (3/3): Club Tijuana de Caliente v Club Santos Laguna: dc:1x @1.26; CA Central Cordoba SE v Velez Sarsfield: dc:x2 @1.26; Queretaro FC v CF Cruz Azul: dc:12 @1.28
- A2 three favourites @3.00 — lost (2/3): Liga Deportiva Alajuelense v Perez Zeledon: 1x2:home @1.30; Los Angeles FC v Los Angeles Galaxy: 1x2:home @1.54; CA Barracas Central v Estudiantes Rio Cuarto: 1x2:home @1.50
- A3 mixed safe @2.03 — LANDED (3/3): Club Tijuana de Caliente v Club Santos Laguna: dc:1x @1.26; CA Central Cordoba SE v Velez Sarsfield: dc:x2 @1.26; Queretaro FC v CF Cruz Azul: dc:12 @1.28
- A4 three draw-proof @1.94 — LANDED (3/3): CF America v CF Pachuca: dc:12 @1.24; CA Barracas Central v Estudiantes Rio Cuarto: dc:12 @1.24; Club Tijuana de Caliente v Club Santos Laguna: dc:12 @1.26

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

