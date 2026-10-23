# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

5549 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 654 | 74% | -0.0% ± 2.3% | -0.1% | £99.96 | -4.1% / +0.7% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 1768 | 57% | -1.3% ± 2.1% | -0.0% | £77.70 | +0.3% / -1.5% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 1328 | 29% | -10.1% ± 3.9% | -0.8% | £-33.98 | -6.2% / -10.7% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 913 | 26% | -14.1% ± 4.8% | -0.3% | £-28.77 | -39.5% / -10.5% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 2224 | 62% | -2.5% ± 1.6% | -0.0% | £45.05 | +0.2% / -3.0% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 1230 | 56% | -8.3% ± 2.3% | -0.9% | £-2.48 | -11.2% / -8.1% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 1482 | 48% | -15.4% ± 2.3% | -0.3% | £-128.73 | -29.0% / -14.1% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 2712 | 77% | -3.1% ± 1.0% | -0.3% | £15.78 | +6.3% / -4.5% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 3262 | 75% | -5.4% ± 1.0% | -0.1% | £-74.76 | +1.8% / -6.4% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 2057 | 51% | +0.9% ± 2.2% | -0.5% | £119.48 | +10.8% / -0.3% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 26 | 88% | +3.2% ± 7.5% | -2.4% | £100.83 | +1.4% / +3.8% | learning (26/100 bets) |
| F12 strong home, plain | home win on F11's games | 26 | 88% | +4.4% ± 7.6% | -2.3% | £101.15 | +2.4% / +5.2% | learning (26/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 26 | 96% | +0.5% ± 4.0% | -0.9% | £100.13 | -10.1% / +4.4% | learning (26/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 133 | 61% | +0.2% ± 7.1% | +1.4% | £100.26 | -4.6% / +10.6% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 133 | 62% | +1.9% ± 7.0% | +1.2% | £102.55 | -1.5% / +9.3% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 13 | 85% | +4.6% ± 13.1% | +1.8% | £100.60 | +30.4% / -11.5% | learning (13/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 6 | 67% | +16.8% ± 37.3% | +1.9% | £101.01 | +72.0% / -10.8% | learning (6/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 67 | 60% | -17.1% ± 8.4% | -4.0% | £88.57 | -12.2% / -24.2% | learning (67/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 288 | 68% | -6.4% ± 3.8% | +0.2% | £81.63 | +7.8% / -7.7% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 331 | 39% | -3.5% ± 6.8% | -1.5% | £88.54 | +5.3% / -4.3% | no edge shown |
| B3 main total under | Under the main total line | 834 | 47% | -13.0% ± 3.2% | -0.2% | £-8.76 | -13.5% / -13.0% | losing — avoid |
| B4 main total over | Over the main total line | 834 | 53% | -1.6% ± 3.2% | +0.1% | £86.41 | +0.8% / -1.8% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 170: 95 draw(s), 75 beaten |
| F2 mid favourite | lost 762: 410 draw(s), 352 beaten |
| F3 home underdog | lost 942: 354 draw(s), 588 beaten |
| F4 draw, tight game | lost 673; goals in those games avg 3.1 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.9, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.5 |
| F7 BTTS no | lost 777; goals in those games avg 3.7 |
| F8 safe double chance | lost 634; goals in those games avg 2.5 |
| F9 draw-proof | lost 827; goals in those games avg 2.2 |
| F10 mid-price home | lost 1012: 519 draw(s), 493 beaten |
| F11 2UP strong home | won 23 (0 only by the early payout), lost 3 |
| F12 strong home, plain | lost 3: 2 draw(s), 1 beaten |
| F13 strong home, double chance | lost 1; goals in those games avg 5.0 |
| P1 profile: BTTS yes | lost 52; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +2.1, losses -1.2 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.4, losses +1.5 |
| P4 profile: BTTS no | lost 2; goals in those games avg 2.5 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.7, losses +1.4 |
| B1 home favourite | lost 92 by 8 pts on average |
| B2 away underdog | lost 203 by 14 pts on average |
| B3 main total under | total vs line (pts): wins -13.0, losses +15.2 |
| B4 main total over | total vs line (pts): wins +15.2, losses -13.0 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 16 | 7/16 | -22.7% | 44% vs 46% | 39/48 |
| A2 three favourites | 3 legs from F1 + F2 | 17 | 9/17 | +11.7% | 53% vs 41% | 41/51 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 17 | 3/17 | -68.7% | 18% vs 47% | 35/51 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 15 | 7/15 | -18.4% | 47% vs 46% | 35/45 |

Latest accas (2026-10-23):
- A2 three favourites @3.79 — lost (1/3): Ferrymead Bays v Cashmere Technical: 1x2:away @1.30; Shanghai Port B v Hangzhou Linping Wuyue: 1x2:home @1.56; Always Ready v The Strongest: 1x2:home @1.87
- A3 mixed safe @2.16 — lost (2/3): Always Ready v The Strongest: dc:12 @1.25; Alebrijes de Oaxaca FC v Cruz Azul Hidalgo: dc:12 @1.27; Oklahoma City Thunder v Denver Nuggets: win:home @1.36
- A4 three draw-proof @1.94 — lost (2/3): Shanghai Port B v Hangzhou Linping Wuyue: dc:12 @1.22; Always Ready v The Strongest: dc:12 @1.25; Alebrijes de Oaxaca FC v Cruz Azul Hidalgo: dc:12 @1.27

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

