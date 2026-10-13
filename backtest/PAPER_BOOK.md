# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

2396 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 249 | 72% | -1.9% ± 3.9% | -0.4% | £95.23 | -2.3% / -1.9% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 795 | 57% | -1.3% ± 3.1% | +0.2% | £89.84 | +8.4% / -2.2% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 593 | 29% | -11.7% ± 5.8% | -0.5% | £30.80 | -16.2% / -11.0% | no edge shown |
| F4 draw, tight game | draw when the two win prices are within 25% | 428 | 26% | -15.7% ± 7.0% | -0.1% | £32.60 | -39.1% / -12.7% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 1010 | 61% | -5.1% ± 2.4% | -0.3% | £47.99 | -1.0% / -6.0% | losing — avoid |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 604 | 57% | -5.1% ± 3.4% | -0.7% | £69.43 | -5.9% / -5.0% | no edge shown |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 719 | 48% | -15.3% ± 3.3% | +0.0% | £-9.71 | -30.9% / -13.7% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 1244 | 76% | -3.7% ± 1.5% | -0.3% | £54.42 | +9.2% / -5.4% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 1451 | 75% | -4.5% ± 1.4% | -0.1% | £34.99 | +3.2% / -5.6% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 931 | 50% | -0.8% ± 3.3% | -0.5% | £92.49 | +8.4% / -1.8% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 5 | 100% | +15.6% ± 3.5% | +0.0% | £100.78 | — / +15.6% | learning (5/100 bets) |
| F12 strong home, plain | home win on F11's games | 5 | 100% | +17.0% ± 4.0% | +0.0% | £100.85 | — / +17.0% | learning (5/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 5 | 100% | +4.0% ± 1.3% | +0.0% | £100.20 | — / +4.0% | learning (5/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 109 | 68% | -5.4% ± 6.3% | -0.5% | £94.08 | +9.4% / -6.1% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 132 | 39% | -1.2% ± 11.0% | -0.3% | £98.42 | +24.2% / -2.4% | no edge shown |
| B3 main total under | Under the main total line | 329 | 47% | -12.7% ± 5.1% | -0.3% | £58.38 | -50.0% / -10.9% | losing — avoid |
| B4 main total over | Over the main total line | 329 | 53% | -2.0% ± 5.1% | +0.1% | £93.56 | +37.3% / -3.8% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 69: 36 draw(s), 33 beaten |
| F2 mid favourite | lost 341: 174 draw(s), 167 beaten |
| F3 home underdog | lost 422: 154 draw(s), 268 beaten |
| F4 draw, tight game | lost 318; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.7, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 374; goals in those games avg 3.7 |
| F8 safe double chance | lost 297; goals in those games avg 2.4 |
| F9 draw-proof | lost 358; goals in those games avg 2.2 |
| F10 mid-price home | lost 468: 230 draw(s), 238 beaten |
| F11 2UP strong home | won 5 (0 only by the early payout), lost 0 |
| F12 strong home, plain | no loss yet |
| F13 strong home, double chance | no loss yet |
| B1 home favourite | lost 35 by 9 pts on average |
| B2 away underdog | lost 80 by 12 pts on average |
| B3 main total under | total vs line (pts): wins -12.6, losses +16.7 |
| B4 main total over | total vs line (pts): wins +16.7, losses -12.6 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 7 | 3/7 | -20.6% | 43% vs 45% | 17/21 |
| A2 three favourites | 3 legs from F1 + F2 | 7 | 3/7 | +4.1% | 43% vs 37% | 16/21 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 7 | 2/7 | -46.9% | 29% vs 46% | 14/21 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 5 | 3/5 | +4.8% | 60% vs 46% | 12/15 |

Latest accas (2026-10-13):
- A1 three safe double chances @2.01 — LANDED (3/3): Pitbulls Santa Barbara FC v Aserri FC: dc:1x @1.20; Red Bull Bragantino SP v Cruzeiro EC MG: dc:12 @1.29; Botafogo FC SP v Ceara SC CE: dc:1x @1.30
- A2 three favourites @3.81 — lost (1/3): Dragones de Oaxaca v Guerreros Del Pacífico FC: 1x2:home @1.43; Waterhouse FC v Tru-Juice FC: 1x2:home @1.54; Pitbulls Santa Barbara FC v Aserri FC: 1x2:home @1.73
- A3 mixed safe @1.89 — LANDED (3/3): Dorados de Chihuahua v Gambusinos De Fresnillo: win:home @1.22; Pitbulls Santa Barbara FC v Aserri FC: dc:1x @1.20; Red Bull Bragantino SP v Cruzeiro EC MG: dc:12 @1.29
- A4 three draw-proof @1.95 — lost (1/3): Waterhouse FC v Tru-Juice FC: dc:12 @1.21; Pitbulls Santa Barbara FC v Aserri FC: dc:12 @1.25; Red Bull Bragantino SP v Cruzeiro EC MG: dc:12 @1.29

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

