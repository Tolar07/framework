# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

525 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 61 | 77% | +3.3% ± 7.3% | -0.4% | £102.03 | -3.0% / +3.8% | learning (61/100 bets) |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 148 | 59% | +1.4% ± 7.0% | +0.5% | £102.10 | -26.0% / +2.8% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 108 | 31% | -0.8% ± 14.4% | +0.5% | £99.16 | -22.9% / +0.8% | no edge shown |
| F4 draw, tight game | draw when the two win prices are within 25% | 63 | 32% | +3.9% ± 19.4% | -0.8% | £102.46 | -17.5% / +5.4% | learning (63/100 bets) |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 202 | 61% | -4.8% ± 5.4% | -0.0% | £90.33 | -35.1% / -2.0% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 133 | 56% | -6.8% ± 7.2% | -0.5% | £90.93 | -3.4% / -7.0% | no edge shown |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 174 | 51% | -11.5% ± 6.6% | +0.1% | £80.01 | -40.7% / -9.9% | no edge shown |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 234 | 75% | -5.2% ± 3.6% | -0.1% | £87.74 | +13.3% / -6.7% | no edge shown |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 230 | 78% | -1.2% ± 3.5% | -0.1% | £97.14 | +8.0% / -2.1% | no edge shown |
| F10 mid-price home | home win at 1.60–2.50 | 136 | 54% | +7.3% ± 8.6% | -1.6% | £109.95 | +2.2% / +7.8% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 0 | — | — | — | £100.00 | — | learning (0/100 bets) |
| F12 strong home, plain | home win on F11's games | 0 | — | — | — | £100.00 | — | learning (0/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 0 | — | — | — | £100.00 | — | learning (0/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 32 | 69% | -4.6% ± 11.7% | -0.1% | £98.53 | -35.0% / -2.6% | learning (32/100 bets) |
| B2 away underdog | away winner at 2.00–3.50 | 46 | 37% | -8.9% ± 18.1% | -0.9% | £95.90 | +167.5% / -16.9% | learning (46/100 bets) |
| B3 main total under | Under the main total line | 118 | 46% | -15.2% ± 8.5% | -0.1% | £82.10 | -53.2% / -12.4% | no edge shown |
| B4 main total over | Over the main total line | 118 | 54% | +1.1% ± 8.6% | +0.1% | £101.24 | +41.3% / -1.9% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 14: 7 draw(s), 7 beaten |
| F2 mid favourite | lost 60: 27 draw(s), 33 beaten |
| F3 home underdog | lost 74: 28 draw(s), 46 beaten |
| F4 draw, tight game | lost 43; goals in those games avg 3.3 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.7, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 85; goals in those games avg 3.6 |
| F8 safe double chance | lost 59; goals in those games avg 2.5 |
| F9 draw-proof | lost 51; goals in those games avg 2.1 |
| F10 mid-price home | lost 62: 27 draw(s), 35 beaten |
| F11 2UP strong home | — |
| F12 strong home, plain | — |
| F13 strong home, double chance | — |
| B1 home favourite | lost 10 by 7 pts on average |
| B2 away underdog | lost 29 by 12 pts on average |
| B3 main total under | total vs line (pts): wins -13.5, losses +18.1 |
| B4 main total over | total vs line (pts): wins +18.1, losses -13.5 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 4 | 1/4 | -55.4% | 25% vs 45% | 9/12 |
| A2 three favourites | 3 legs from F1 + F2 | 4 | 3/4 | +105.0% | 75% vs 33% | 11/12 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 4 | 1/4 | -54.3% | 25% vs 45% | 9/12 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 2 | 0/2 | -100.0% | 0% vs 46% | 4/6 |

Latest accas (2026-10-10):
- A1 three safe double chances @1.86 — lost (2/3): Sagan Tosu v Fujieda MYFC: dc:1x @1.22; AD Carmelita v Guadalupe FC: dc:1x @1.24; Reboceros de La Piedad v Los Cabos United: dc:1x @1.23
- A2 three favourites @2.78 — LANDED (3/3): Wellington Phoenix FC v Birkenhead United AFC: 1x2:away @1.28; Ska-Khabarovsk-2 v FC Kvant Obninsk: 1x2:home @1.45; CD Once Caldas v Llaneros FC: 1x2:home @1.50
- A3 mixed safe @1.86 — lost (2/3): Sagan Tosu v Fujieda MYFC: dc:1x @1.22; AD Carmelita v Guadalupe FC: dc:1x @1.24; Reboceros de La Piedad v Los Cabos United: dc:1x @1.23
- A4 three draw-proof @1.79 — lost (2/3): Tepatitlan FC v Atletico Morelia: dc:12 @1.21; CD Once Caldas v Llaneros FC: dc:12 @1.21; RB Omiya Ardija v Vanraure Hachinohe FC: dc:12 @1.22

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

