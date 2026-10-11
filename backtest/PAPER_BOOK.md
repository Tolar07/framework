# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

1491 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 156 | 68% | -8.0% ± 5.1% | -0.5% | £87.54 | -8.5% / -7.9% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 478 | 57% | -1.8% ± 3.9% | +0.3% | £91.56 | -0.5% / -1.9% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 347 | 29% | -11.9% ± 7.6% | -0.0% | £58.75 | -29.0% / -9.2% | no edge shown |
| F4 draw, tight game | draw when the two win prices are within 25% | 240 | 26% | -13.2% ± 9.5% | -0.4% | £68.41 | -58.0% / -6.3% | no edge shown |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 689 | 61% | -5.6% ± 2.9% | -0.2% | £61.48 | -4.9% / -5.7% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 326 | 57% | -6.1% ± 4.6% | -0.6% | £80.03 | +4.2% / -7.2% | no edge shown |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 435 | 49% | -12.8% ± 4.3% | +0.3% | £44.12 | -24.0% / -11.7% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 809 | 77% | -3.2% ± 1.9% | -0.2% | £74.26 | +14.1% / -5.4% | no edge shown |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 898 | 76% | -4.4% ± 1.8% | -0.0% | £60.92 | +1.7% / -5.2% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 559 | 49% | -3.5% ± 4.2% | -0.9% | £80.48 | +0.2% / -3.9% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 4 | 100% | +13.5% ± 3.7% | +0.0% | £100.54 | — / +13.5% | learning (4/100 bets) |
| F12 strong home, plain | home win on F11's games | 4 | 100% | +14.8% ± 4.3% | +0.0% | £100.59 | — / +14.8% | learning (4/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 4 | 100% | +3.5% ± 1.6% | +0.0% | £100.14 | — / +3.5% | learning (4/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 72 | 67% | -6.3% ± 7.9% | -0.3% | £95.44 | +4.0% / -6.9% | learning (72/100 bets) |
| B2 away underdog | away winner at 2.00–3.50 | 93 | 42% | +3.0% ± 12.9% | -0.5% | £102.78 | +33.8% / +1.6% | learning (93/100 bets) |
| B3 main total under | Under the main total line | 228 | 45% | -16.2% ± 6.1% | -0.3% | £63.12 | -37.5% / -15.0% | losing — avoid |
| B4 main total over | Over the main total line | 228 | 55% | +1.7% ± 6.1% | +0.2% | £103.98 | +25.2% / +0.4% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 50: 26 draw(s), 24 beaten |
| F2 mid favourite | lost 206: 98 draw(s), 108 beaten |
| F3 home underdog | lost 247: 86 draw(s), 161 beaten |
| F4 draw, tight game | lost 177; goals in those games avg 3.2 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.7, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.3, losses +1.5 |
| F7 BTTS no | lost 220; goals in those games avg 3.7 |
| F8 safe double chance | lost 189; goals in those games avg 2.5 |
| F9 draw-proof | lost 219; goals in those games avg 2.3 |
| F10 mid-price home | lost 286: 139 draw(s), 147 beaten |
| F11 2UP strong home | won 4 (0 only by the early payout), lost 0 |
| F12 strong home, plain | no loss yet |
| F13 strong home, double chance | no loss yet |
| B1 home favourite | lost 24 by 8 pts on average |
| B2 away underdog | lost 54 by 12 pts on average |
| B3 main total under | total vs line (pts): wins -13.1, losses +17.1 |
| B4 main total over | total vs line (pts): wins +17.1, losses -13.1 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 5 | 2/5 | -29.1% | 40% vs 46% | 12/15 |
| A2 three favourites | 3 legs from F1 + F2 | 5 | 2/5 | +8.3% | 40% vs 36% | 12/15 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 5 | 1/5 | -63.4% | 20% vs 47% | 11/15 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 3 | 2/3 | +17.6% | 67% vs 46% | 8/9 |

Latest accas (2026-10-11):
- A1 three safe double chances @1.74 — lost (2/3): CD Malacateco v CD Guastatoya: dc:1x @1.20; CS Herediano v AD San Carlos: dc:1x @1.20; Wellington Phoenix v West Coast Rangers FC: dc:12 @1.21
- A2 three favourites @2.73 — lost (2/3): Irapuato v Tritones Vallarta MFC: 1x2:home @1.31; Vaqueros Reynosa FC v Saltillo Soccer FC: 1x2:home @1.36; Diriangen FC Diriamba v CD Walter Ferretti: 1x2:home @1.53
- A3 mixed safe @1.74 — lost (2/3): CD Malacateco v CD Guastatoya: dc:1x @1.20; CS Herediano v AD San Carlos: dc:1x @1.20; Wellington Phoenix v West Coast Rangers FC: dc:12 @1.21
- A4 three draw-proof @1.79 — LANDED (3/3): New Mexico United v Monterey Bay FC: dc:12 @1.21; Wellington Phoenix v West Coast Rangers FC: dc:12 @1.21; Diriangen FC Diriamba v CD Walter Ferretti: dc:12 @1.22

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

