# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

9822 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 1145 | 72% | -1.9% ± 1.8% | -0.2% | £77.97 | +2.0% / -2.5% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 3114 | 56% | -2.9% ± 1.6% | -0.2% | £9.75 | +0.4% / -3.3% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 2334 | 30% | -8.1% ± 3.0% | -0.7% | £-89.32 | -10.8% / -7.7% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 1592 | 26% | -13.4% ± 3.6% | -0.4% | £-113.03 | -16.9% / -12.9% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 3805 | 62% | -3.1% ± 1.2% | -0.1% | £-16.09 | -1.5% / -3.3% | losing — avoid |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 2041 | 55% | -9.2% ± 1.8% | -1.0% | £-88.56 | -10.8% / -9.1% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 2432 | 47% | -15.7% ± 1.8% | -0.4% | £-282.91 | -19.4% / -15.4% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 4797 | 76% | -4.4% ± 0.8% | -0.3% | £-113.09 | +0.0% / -5.1% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 5771 | 74% | -5.7% ± 0.7% | -0.1% | £-229.94 | -1.0% / -6.4% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 3668 | 49% | -2.0% ± 1.7% | -0.3% | £28.00 | +8.9% / -3.4% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 42 | 79% | -8.5% ± 7.5% | -1.9% | £96.44 | -22.7% / -2.8% | learning (42/100 bets) |
| F12 strong home, plain | home win on F11's games | 42 | 76% | -10.4% ± 7.9% | -1.9% | £95.64 | -22.0% / -5.7% | learning (42/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 42 | 90% | -5.5% ± 4.8% | -0.8% | £97.67 | -13.2% / -2.5% | learning (42/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 340 | 58% | -5.3% ± 4.5% | +1.3% | £82.07 | -9.6% / +4.4% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 340 | 59% | -2.4% ± 4.6% | +0.5% | £91.69 | -6.1% / +5.7% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 29 | 86% | +7.3% ± 8.2% | +0.7% | £102.12 | +30.5% / +1.3% | learning (29/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 10 | 50% | -7.9% ± 31.1% | +2.1% | £99.21 | +72.0% / -27.9% | learning (10/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 191 | 63% | -13.4% ± 4.9% | -3.0% | £74.34 | -13.9% / -12.6% | losing — avoid |
| B1 home favourite | home winner at 1.20–1.60 | 488 | 67% | -8.0% ± 2.9% | -0.3% | £60.79 | -0.9% / -8.6% | losing — avoid |
| B2 away underdog | away winner at 2.00–3.50 | 550 | 39% | -3.9% ± 5.3% | -0.5% | £78.68 | +13.8% / -5.5% | no edge shown |
| B3 main total under | Under the main total line | 1450 | 48% | -11.2% ± 2.4% | -0.1% | £-62.21 | -5.9% / -11.6% | losing — avoid |
| B4 main total over | Over the main total line | 1450 | 52% | -3.5% ± 2.4% | -0.0% | £49.60 | -5.9% / -3.3% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 317: 177 draw(s), 140 beaten |
| F2 mid favourite | lost 1371: 712 draw(s), 659 beaten |
| F3 home underdog | lost 1640: 594 draw(s), 1046 beaten |
| F4 draw, tight game | lost 1171; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 1279; goals in those games avg 3.7 |
| F8 safe double chance | lost 1170; goals in those games avg 2.5 |
| F9 draw-proof | lost 1477; goals in those games avg 2.2 |
| F10 mid-price home | lost 1860: 951 draw(s), 909 beaten |
| F11 2UP strong home | won 33 (1 only by the early payout), lost 9 |
| F12 strong home, plain | lost 10: 6 draw(s), 4 beaten |
| F13 strong home, double chance | lost 4; goals in those games avg 4.0 |
| P1 profile: BTTS yes | lost 144; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +1.9, losses -1.1 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.8, losses +1.0 |
| P4 profile: BTTS no | lost 5; goals in those games avg 4.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.6, losses +1.3 |
| B1 home favourite | lost 160 by 9 pts on average |
| B2 away underdog | lost 338 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -13.4, losses +15.1 |
| B4 main total over | total vs line (pts): wins +15.1, losses -13.4 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 26 | 11/26 | -25.6% | 42% vs 46% | 60/78 |
| A2 three favourites | 3 legs from F1 + F2 | 26 | 14/26 | +8.0% | 54% vs 43% | 64/78 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 26 | 9/26 | -38.9% | 35% vs 47% | 59/78 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 24 | 11/24 | -19.7% | 46% vs 47% | 55/72 |

Latest accas (2026-11-01):
- A1 three safe double chances @1.80 — lost (2/3): Cancun FC v Jaiba Brava: dc:1x @1.21; AD Isidro Metapan v Municipal Limeno: dc:1x @1.22; Cashmere Technical v Auckland City FC: dc:12 @1.22
- A2 three favourites @2.28 — lost (2/3): Piratas Veracruz v CD Tapatio: 1x2:home @1.31; Irapuato v Deportiva Venados: 1x2:home @1.30; Birkenhead United AFC v Ferrymead Bays: 1x2:home @1.34
- A3 mixed safe @1.77 — LANDED (3/3): Memphis Grizzlies v Sacramento Kings: win:home @1.20; Cancun FC v Jaiba Brava: dc:1x @1.21; AD Isidro Metapan v Municipal Limeno: dc:1x @1.22
- A4 three draw-proof @1.79 — lost (1/3): CF Monterrey v Club Tijuana de Caliente: dc:12 @1.20; CD Choloma v CD Olimpia Tegucigalpa: dc:12 @1.22; Cashmere Technical v Auckland City FC: dc:12 @1.22

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

