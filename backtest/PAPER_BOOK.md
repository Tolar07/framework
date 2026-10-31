# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

8820 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 1036 | 73% | -1.6% ± 1.9% | -0.1% | £83.09 | +1.5% / -2.1% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 2790 | 56% | -3.3% ± 1.6% | -0.1% | £7.27 | -1.4% / -3.5% | losing — avoid |
| F3 home underdog | home win at 2.50–5.00 | 2085 | 29% | -8.5% ± 3.2% | -0.8% | £-76.96 | -13.7% / -7.7% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 1418 | 26% | -13.7% ± 3.8% | -0.3% | £-94.53 | -26.8% / -11.9% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 3400 | 63% | -2.4% ± 1.3% | -0.1% | £19.92 | -0.7% / -2.7% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 1853 | 56% | -7.8% ± 1.9% | -0.9% | £-43.62 | -6.3% / -7.9% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 2213 | 48% | -15.0% ± 1.9% | -0.4% | £-230.95 | -19.9% / -14.5% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 4241 | 75% | -4.6% ± 0.8% | -0.3% | £-95.34 | +0.6% / -5.4% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 5116 | 74% | -5.7% ± 0.8% | -0.1% | £-192.01 | -0.6% / -6.5% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 3257 | 49% | -2.5% ± 1.8% | -0.4% | £18.53 | +7.6% / -3.8% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 36 | 83% | -2.4% ± 7.4% | -2.1% | £99.13 | -21.1% / +3.8% | learning (36/100 bets) |
| F12 strong home, plain | home win on F11's games | 36 | 81% | -4.7% ± 8.0% | -2.1% | £98.31 | -20.3% / +0.5% | learning (36/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 36 | 92% | -4.1% ± 4.9% | -0.9% | £98.53 | -18.3% / +0.7% | learning (36/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 291 | 59% | -3.5% ± 4.8% | +1.6% | £89.88 | -8.0% / +5.9% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 291 | 58% | -3.0% ± 4.9% | +1.0% | £91.26 | -7.6% / +6.4% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 22 | 86% | +7.2% ± 9.4% | +1.2% | £101.59 | +30.5% / -1.5% | learning (22/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 10 | 50% | -7.9% ± 31.1% | +2.1% | £99.21 | +72.0% / -27.9% | learning (10/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 166 | 65% | -10.4% ± 5.1% | -3.3% | £82.78 | -7.8% / -14.2% | losing — avoid |
| B1 home favourite | home winner at 1.20–1.60 | 439 | 68% | -6.7% ± 3.1% | -0.2% | £70.74 | -1.4% / -7.1% | losing — avoid |
| B2 away underdog | away winner at 2.00–3.50 | 502 | 38% | -4.4% ± 5.5% | -0.6% | £77.91 | +16.3% / -6.5% | no edge shown |
| B3 main total under | Under the main total line | 1305 | 48% | -11.6% ± 2.6% | -0.1% | £-50.74 | -3.8% / -12.1% | losing — avoid |
| B4 main total over | Over the main total line | 1305 | 52% | -3.1% ± 2.6% | +0.0% | £60.13 | -8.1% / -2.7% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 284: 157 draw(s), 127 beaten |
| F2 mid favourite | lost 1234: 640 draw(s), 594 beaten |
| F3 home underdog | lost 1470: 535 draw(s), 935 beaten |
| F4 draw, tight game | lost 1043; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 1153; goals in those games avg 3.7 |
| F8 safe double chance | lost 1041; goals in those games avg 2.5 |
| F9 draw-proof | lost 1310; goals in those games avg 2.2 |
| F10 mid-price home | lost 1661: 841 draw(s), 820 beaten |
| F11 2UP strong home | won 30 (1 only by the early payout), lost 6 |
| F12 strong home, plain | lost 7: 4 draw(s), 3 beaten |
| F13 strong home, double chance | lost 3; goals in those games avg 3.7 |
| P1 profile: BTTS yes | lost 120; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +1.9, losses -1.1 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.7, losses +1.2 |
| P4 profile: BTTS no | lost 5; goals in those games avg 4.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.7, losses +1.3 |
| B1 home favourite | lost 139 by 9 pts on average |
| B2 away underdog | lost 310 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -13.3, losses +15.1 |
| B4 main total over | total vs line (pts): wins +15.1, losses -13.3 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 25 | 11/25 | -22.6% | 44% vs 46% | 58/75 |
| A2 three favourites | 3 legs from F1 + F2 | 25 | 13/25 | +5.1% | 52% vs 42% | 62/75 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 25 | 7/25 | -50.7% | 28% vs 47% | 55/75 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 23 | 10/23 | -23.7% | 43% vs 47% | 52/69 |

Latest accas (2026-10-31):
- A1 three safe double chances @1.86 — lost (2/3): Oriente Petrolero v Club Aurora: dc:1x @1.21; Miramar Rangers v Wellington Olympic: dc:12 @1.23; CF Correcaminos UAT v Venados  FC: dc:12 @1.25
- A2 three favourites @3.53 — lost (2/3): Guerreros Del Pacífico FC v Heroes de Zaci FC: 1x2:home @1.44; Reboceros de La Piedad v Inter Playa Del Carmen: 1x2:home @1.54; Racing Club Avellaneda v CA Aldosivi: 1x2:home @1.59
- A3 mixed safe @1.86 — lost (2/3): Oriente Petrolero v Club Aurora: dc:1x @1.21; Miramar Rangers v Wellington Olympic: dc:12 @1.23; CF Correcaminos UAT v Venados  FC: dc:12 @1.25
- A4 three draw-proof @1.81 — lost (1/3): Reboceros de La Piedad v Inter Playa Del Carmen: dc:12 @1.20; Oriente Petrolero v Club Aurora: dc:12 @1.23; Inter Santa Tecla v CD Platense Municipal Zacatecoluca: dc:12 @1.23

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

