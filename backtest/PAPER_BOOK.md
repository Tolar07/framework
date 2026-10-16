# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

2977 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 333 | 75% | +1.3% ± 3.3% | -0.0% | £104.47 | -0.2% / +1.6% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 947 | 58% | +0.1% ± 2.8% | +0.0% | £100.53 | +8.6% / -0.8% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 699 | 28% | -14.7% ± 5.3% | -0.2% | £-2.66 | -10.8% / -15.3% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 500 | 25% | -16.8% ± 6.4% | -0.2% | £16.23 | -43.4% / -13.1% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 1237 | 62% | -3.4% ± 2.2% | -0.1% | £58.33 | +1.5% / -4.4% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 701 | 56% | -7.0% ± 3.1% | -0.9% | £50.88 | -6.0% / -7.1% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 848 | 47% | -17.2% ± 3.0% | -0.2% | £-45.91 | -33.0% / -15.6% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 1476 | 77% | -3.1% ± 1.4% | -0.3% | £54.05 | +11.1% / -5.1% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 1745 | 75% | -4.4% ± 1.3% | -0.1% | £23.92 | +4.7% / -5.6% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 1119 | 50% | -1.3% ± 3.0% | -0.5% | £85.46 | +8.2% / -2.4% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 10 | 90% | +4.2% ± 11.7% | -1.9% | £100.42 | — / +4.2% | learning (10/100 bets) |
| F12 strong home, plain | home win on F11's games | 10 | 90% | +5.3% ± 11.9% | -2.1% | £100.53 | — / +5.3% | learning (10/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 10 | 100% | +4.1% ± 0.7% | -0.7% | £100.41 | — / +4.1% | learning (10/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 12 | 67% | +9.4% ± 23.7% | -0.4% | £101.13 | +0.9% / +26.5% | learning (12/100 bets) |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 12 | 83% | +35.5% ± 19.1% | -0.5% | £104.26 | +34.2% / +38.0% | learning (12/100 bets) |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 2 | 100% | +25.5% ± 8.5% | +2.3% | £100.51 | +34.0% / +17.0% | learning (2/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 3 | 67% | +16.3% ± 58.4% | +2.3% | £100.49 | +84.0% / -17.5% | learning (3/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 5 | 40% | -46.0% ± 33.1% | -0.4% | £97.70 | -100.0% / -32.5% | learning (5/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 152 | 66% | -8.2% ± 5.4% | -0.9% | £87.57 | +17.5% / -11.0% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 183 | 42% | +4.5% ± 9.4% | -0.3% | £108.30 | +6.1% / +4.4% | no edge shown |
| B3 main total under | Under the main total line | 446 | 46% | -14.3% ± 4.4% | -0.2% | £36.03 | -17.8% / -14.1% | losing — avoid |
| B4 main total over | Over the main total line | 446 | 54% | -0.3% ± 4.4% | +0.1% | £98.82 | +4.6% / -0.7% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 84: 42 draw(s), 42 beaten |
| F2 mid favourite | lost 399: 209 draw(s), 190 beaten |
| F3 home underdog | lost 504: 179 draw(s), 325 beaten |
| F4 draw, tight game | lost 373; goals in those games avg 3.1 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.5 |
| F7 BTTS no | lost 451; goals in those games avg 3.7 |
| F8 safe double chance | lost 346; goals in those games avg 2.4 |
| F9 draw-proof | lost 429; goals in those games avg 2.2 |
| F10 mid-price home | lost 564: 275 draw(s), 289 beaten |
| F11 2UP strong home | won 9 (0 only by the early payout), lost 1 |
| F12 strong home, plain | lost 1: 1 draw(s), 0 beaten |
| F13 strong home, double chance | no loss yet |
| P1 profile: BTTS yes | lost 4; goals in those games avg 2.8 |
| P2 profile: over 2.5 | total vs line (goals): wins +1.9, losses -1.0 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.0, losses — |
| P4 profile: BTTS no | lost 1; goals in those games avg 3.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.0, losses +1.2 |
| B1 home favourite | lost 51 by 8 pts on average |
| B2 away underdog | lost 107 by 12 pts on average |
| B3 main total under | total vs line (pts): wins -12.7, losses +15.7 |
| B4 main total over | total vs line (pts): wins +15.7, losses -12.7 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 10 | 6/10 | +7.6% | 60% vs 46% | 26/30 |
| A2 three favourites | 3 legs from F1 + F2 | 10 | 5/10 | +9.4% | 50% vs 40% | 25/30 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 10 | 4/10 | -27.6% | 40% vs 47% | 22/30 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 8 | 4/8 | -12.5% | 50% vs 46% | 19/24 |

Latest accas (2026-10-16):
- A1 three safe double chances @1.92 — LANDED (3/3): Deportivo Saprissa San Jose v Sporting FC: dc:1x @1.22; CD Suchitepequez v Deportivo San Pedro: dc:1x @1.25; CD Olimpia Tegucigalpa v Real CD Espana San Pedro Sula: dc:1x @1.26
- A2 three favourites @2.98 — lost (2/3): Real Esteli FC v Art Municipal Jalapa: 1x2:home @1.27; CD Luis Angel Firpo Usulutan v CD Inca: 1x2:home @1.28; Deportivo Saprissa San Jose v Sporting FC: 1x2:home @1.83
- A3 mixed safe @1.92 — LANDED (3/3): Deportivo Saprissa San Jose v Sporting FC: dc:1x @1.22; CD Suchitepequez v Deportivo San Pedro: dc:1x @1.25; CD Olimpia Tegucigalpa v Real CD Espana San Pedro Sula: dc:1x @1.26
- A4 three draw-proof @2.10 — lost (2/3): Deportivo Saprissa San Jose v Sporting FC: dc:12 @1.27; CD Olimpia Tegucigalpa v Real CD Espana San Pedro Sula: dc:12 @1.28; CD Suchitepequez v Deportivo San Pedro: dc:12 @1.29

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

