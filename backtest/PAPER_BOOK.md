# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

7803 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 905 | 73% | -1.1% ± 2.0% | -0.1% | £90.22 | +2.1% / -1.6% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 2493 | 56% | -3.3% ± 1.7% | -0.1% | £17.25 | -1.6% / -3.5% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 1863 | 29% | -9.6% ± 3.3% | -0.7% | £-78.61 | -10.3% / -9.5% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 1289 | 27% | -13.1% ± 4.0% | -0.3% | £-68.80 | -24.8% / -11.5% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 3076 | 63% | -2.1% ± 1.4% | -0.1% | £35.33 | -1.7% / -2.2% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 1714 | 56% | -8.4% ± 2.0% | -1.0% | £-43.24 | -7.7% / -8.4% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 2040 | 48% | -15.5% ± 2.0% | -0.4% | £-215.59 | -20.0% / -15.1% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 3845 | 76% | -4.5% ± 0.9% | -0.3% | £-72.03 | +1.6% / -5.4% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 4622 | 74% | -5.8% ± 0.8% | -0.1% | £-169.18 | -0.8% / -6.6% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 2950 | 49% | -2.5% ± 1.9% | -0.4% | £27.53 | +7.4% / -3.8% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 33 | 88% | +2.8% ± 6.8% | -2.3% | £100.93 | -11.3% / +7.3% | learning (33/100 bets) |
| F12 strong home, plain | home win on F11's games | 33 | 85% | +0.3% ± 7.5% | -2.2% | £100.10 | -10.4% / +3.7% | learning (33/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 33 | 94% | -1.8% ± 4.4% | -0.9% | £99.41 | -21.4% / +4.5% | learning (33/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 248 | 57% | -6.6% ± 5.2% | +1.6% | £83.66 | -9.3% / +0.5% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 248 | 58% | -5.5% ± 5.2% | +1.0% | £86.47 | -9.0% / +3.6% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 16 | 81% | +0.4% ± 12.6% | +1.5% | £100.07 | +30.4% / -13.2% | learning (16/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 9 | 44% | -22.1% ± 30.9% | +2.1% | £98.01 | +72.0% / -49.0% | learning (9/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 138 | 67% | -7.0% ± 5.6% | -3.2% | £90.31 | -3.4% / -13.5% | no edge shown |
| B1 home favourite | home winner at 1.20–1.60 | 394 | 69% | -5.7% ± 3.2% | -0.0% | £77.70 | +2.9% / -6.4% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 441 | 39% | -3.6% ± 5.9% | -0.8% | £84.33 | +13.5% / -5.3% | no edge shown |
| B3 main total under | Under the main total line | 1143 | 48% | -11.2% ± 2.7% | -0.2% | £-28.47 | -8.5% / -11.4% | losing — avoid |
| B4 main total over | Over the main total line | 1143 | 52% | -3.4% ± 2.7% | +0.0% | £60.70 | -3.7% / -3.4% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 244: 139 draw(s), 105 beaten |
| F2 mid favourite | lost 1102: 582 draw(s), 520 beaten |
| F3 home underdog | lost 1317: 489 draw(s), 828 beaten |
| F4 draw, tight game | lost 946; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 1070; goals in those games avg 3.7 |
| F8 safe double chance | lost 940; goals in those games avg 2.5 |
| F9 draw-proof | lost 1188; goals in those games avg 2.2 |
| F10 mid-price home | lost 1504: 770 draw(s), 734 beaten |
| F11 2UP strong home | won 29 (1 only by the early payout), lost 4 |
| F12 strong home, plain | lost 5: 3 draw(s), 2 beaten |
| F13 strong home, double chance | lost 2; goals in those games avg 4.0 |
| P1 profile: BTTS yes | lost 106; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +1.9, losses -1.1 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.6, losses +1.2 |
| P4 profile: BTTS no | lost 5; goals in those games avg 4.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.6, losses +1.4 |
| B1 home favourite | lost 122 by 8 pts on average |
| B2 away underdog | lost 270 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -13.2, losses +14.8 |
| B4 main total over | total vs line (pts): wins +14.8, losses -13.2 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 21 | 10/21 | -14.2% | 48% vs 46% | 50/63 |
| A2 three favourites | 3 legs from F1 + F2 | 20 | 11/20 | +13.1% | 55% vs 42% | 50/60 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 21 | 7/21 | -39.6% | 33% vs 47% | 47/63 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 19 | 9/19 | -15.5% | 47% vs 46% | 45/57 |

Latest accas (2026-10-27):
- A1 three safe double chances @2.16 — LANDED (3/3): Pitbulls Santa Barbara FC v AD Carmelita: dc:12 @1.28; Mount Pleasant FC v Montego Bay United: dc:12 @1.30; Independiente Santa Fe v CA Bucaramanga: dc:1x @1.30
- A3 mixed safe @2.11 — LANDED (3/3): Oklahoma City Thunder v Phoenix Suns: win:home @1.27; Pitbulls Santa Barbara FC v AD Carmelita: dc:12 @1.28; Mount Pleasant FC v Montego Bay United: dc:12 @1.30
- A4 three draw-proof @2.03 — LANDED (3/3): Veraguas United FC v Cocle FC: dc:12 @1.22; Pitbulls Santa Barbara FC v AD Carmelita: dc:12 @1.28; Mount Pleasant FC v Montego Bay United: dc:12 @1.30

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

