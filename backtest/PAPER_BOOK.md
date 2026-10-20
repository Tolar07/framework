# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

5008 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 592 | 74% | -0.5% ± 2.5% | -0.2% | £97.22 | -5.7% / +0.4% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 1631 | 57% | -0.9% ± 2.1% | -0.1% | £85.33 | +0.9% / -1.1% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 1227 | 29% | -10.3% ± 4.1% | -0.6% | £-25.82 | -6.2% / -10.8% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 847 | 26% | -14.0% ± 5.0% | -0.3% | £-18.88 | -42.2% / -10.5% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 2011 | 62% | -3.6% ± 1.7% | -0.1% | £27.39 | -1.2% / -4.1% | losing — avoid |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 1164 | 55% | -8.5% ± 2.4% | -0.8% | £0.64 | -10.1% / -8.4% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 1378 | 48% | -15.2% ± 2.4% | -0.3% | £-109.13 | -24.9% / -14.3% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 2498 | 77% | -3.0% ± 1.1% | -0.3% | £25.99 | +8.2% / -4.5% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 2994 | 75% | -5.0% ± 1.0% | -0.1% | £-50.79 | +4.0% / -6.3% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 1910 | 51% | +0.9% ± 2.3% | -0.5% | £116.58 | +12.0% / -0.5% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 17 | 94% | +9.4% ± 7.0% | -2.5% | £101.59 | +20.0% / +7.9% | learning (17/100 bets) |
| F12 strong home, plain | home win on F11's games | 17 | 94% | +10.5% ± 7.1% | -2.2% | £101.78 | +20.5% / +9.1% | learning (17/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 17 | 100% | +4.3% ± 0.5% | -0.8% | £100.73 | +5.5% / +4.1% | learning (17/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 102 | 59% | -2.8% ± 8.2% | +0.9% | £97.12 | -7.8% / +9.6% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 102 | 62% | +1.1% ± 8.1% | +0.1% | £101.08 | -2.9% / +11.0% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 10 | 90% | +9.7% ± 12.4% | +0.7% | £100.97 | +27.8% / -2.3% | learning (10/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 6 | 67% | +16.8% ± 37.3% | +1.9% | £101.01 | +72.0% / -10.8% | learning (6/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 52 | 62% | -14.6% ± 9.5% | -3.0% | £92.42 | -6.7% / -28.3% | learning (52/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 230 | 67% | -7.2% ± 4.3% | -0.6% | £83.43 | +4.7% / -8.2% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 267 | 38% | -5.1% ± 7.6% | -0.8% | £86.37 | +8.8% / -6.2% | no edge shown |
| B3 main total under | Under the main total line | 685 | 47% | -13.1% ± 3.5% | -0.2% | £10.10 | -26.5% / -12.3% | losing — avoid |
| B4 main total over | Over the main total line | 685 | 53% | -1.6% ± 3.5% | +0.1% | £88.89 | +13.1% / -2.5% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 156: 85 draw(s), 71 beaten |
| F2 mid favourite | lost 700: 374 draw(s), 326 beaten |
| F3 home underdog | lost 871: 323 draw(s), 548 beaten |
| F4 draw, tight game | lost 624; goals in those games avg 3.1 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.9, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.5 |
| F7 BTTS no | lost 720; goals in those games avg 3.7 |
| F8 safe double chance | lost 581; goals in those games avg 2.5 |
| F9 draw-proof | lost 752; goals in those games avg 2.2 |
| F10 mid-price home | lost 940: 482 draw(s), 458 beaten |
| F11 2UP strong home | won 16 (0 only by the early payout), lost 1 |
| F12 strong home, plain | lost 1: 1 draw(s), 0 beaten |
| F13 strong home, double chance | no loss yet |
| P1 profile: BTTS yes | lost 42; goals in those games avg 1.8 |
| P2 profile: over 2.5 | total vs line (goals): wins +2.1, losses -1.2 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.4, losses +1.5 |
| P4 profile: BTTS no | lost 2; goals in those games avg 2.5 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.7, losses +1.5 |
| B1 home favourite | lost 75 by 8 pts on average |
| B2 away underdog | lost 166 by 14 pts on average |
| B3 main total under | total vs line (pts): wins -13.1, losses +15.7 |
| B4 main total over | total vs line (pts): wins +15.7, losses -13.1 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 14 | 7/14 | -11.6% | 50% vs 46% | 35/42 |
| A2 three favourites | 3 legs from F1 + F2 | 14 | 8/14 | +20.8% | 57% vs 40% | 34/42 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 14 | 3/14 | -62.0% | 21% vs 47% | 29/42 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 12 | 6/12 | -12.6% | 50% vs 46% | 28/36 |

Latest accas (2026-10-20):
- A1 three safe double chances @2.00 — lost (2/3): Tapachula Soconusco FC v Deportiva Venados: dc:x2 @1.20; Racing United FC v Waterhouse FC: dc:12 @1.29; CD Escorpiones Belen v Puntarenas FC: dc:12 @1.29
- A2 three favourites @4.49 — lost (1/3): Sporting FC v AD San Carlos: 1x2:home @1.61; AD Cofutpa v Quepos Cambute: 1x2:away @1.67; Antigua GFC v CSD Xelaju MC: 1x2:home @1.67
- A3 mixed safe @1.97 — lost (2/3): Tapachula Soconusco FC v Deportiva Venados: dc:x2 @1.20; Astros de Jalisco v Mineros de Zacatecas: win:home @1.27; Racing United FC v Waterhouse FC: dc:12 @1.29
- A4 three draw-proof @1.86 — lost (2/3): Tapachula Soconusco FC v Deportiva Venados: dc:12 @1.22; AD Cofutpa v Quepos Cambute: dc:12 @1.23; Sporting FC v AD San Carlos: dc:12 @1.24

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

