# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

10871 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 1245 | 73% | -1.0% ± 1.7% | -0.1% | £87.94 | +3.0% / -1.5% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 3410 | 56% | -2.4% ± 1.5% | -0.1% | £19.47 | +2.6% / -3.0% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 2573 | 29% | -9.4% ± 2.8% | -0.6% | £-143.02 | -10.1% / -9.3% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 1731 | 27% | -13.2% ± 3.5% | -0.3% | £-128.49 | -20.5% / -12.1% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 4171 | 62% | -3.5% ± 1.2% | -0.1% | £-43.91 | -3.2% / -3.5% | losing — avoid |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 2377 | 56% | -8.1% ± 1.7% | -0.9% | £-92.90 | -13.3% / -7.8% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 2752 | 48% | -14.7% ± 1.7% | -0.4% | £-305.86 | -17.0% / -14.5% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 5268 | 76% | -4.3% ± 0.7% | -0.3% | £-124.19 | +0.5% / -5.0% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 6338 | 74% | -5.8% ± 0.7% | -0.1% | £-268.18 | -0.1% / -6.7% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 4044 | 50% | -1.3% ± 1.6% | -0.2% | £45.60 | +10.3% / -2.9% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 55 | 84% | -2.1% ± 5.9% | -1.3% | £98.87 | -11.9% / +2.0% | learning (55/100 bets) |
| F12 strong home, plain | home win on F11's games | 55 | 82% | -3.2% ± 6.2% | -1.3% | £98.25 | -11.1% / +0.1% | learning (55/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 55 | 93% | -3.0% ± 3.7% | -0.6% | £98.35 | -8.4% / -0.8% | learning (55/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 412 | 56% | -8.0% ± 4.1% | +1.0% | £67.10 | -11.6% / +1.4% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 412 | 58% | -3.1% ± 4.2% | +0.4% | £87.14 | -6.4% / +5.3% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 32 | 88% | +9.2% ± 7.5% | +0.5% | £102.96 | +30.5% / +4.3% | learning (32/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 10 | 50% | -7.9% ± 31.1% | +2.1% | £99.21 | +72.0% / -27.9% | learning (10/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 222 | 64% | -12.1% ± 4.5% | -2.6% | £73.12 | -11.8% / -12.7% | losing — avoid |
| B1 home favourite | home winner at 1.20–1.60 | 543 | 68% | -7.6% ± 2.8% | -0.3% | £58.57 | -3.2% / -8.0% | losing — avoid |
| B2 away underdog | away winner at 2.00–3.50 | 604 | 39% | -3.8% ± 5.0% | -0.5% | £76.97 | +17.4% / -6.0% | no edge shown |
| B3 main total under | Under the main total line | 1687 | 48% | -10.3% ± 2.3% | -0.1% | £-73.77 | -1.5% / -10.9% | losing — avoid |
| B4 main total over | Over the main total line | 1687 | 52% | -4.3% ± 2.3% | -0.0% | £27.66 | -10.0% / -3.9% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 336: 187 draw(s), 149 beaten |
| F2 mid favourite | lost 1491: 783 draw(s), 708 beaten |
| F3 home underdog | lost 1817: 662 draw(s), 1155 beaten |
| F4 draw, tight game | lost 1271; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 1432; goals in those games avg 3.7 |
| F8 safe double chance | lost 1278; goals in those games avg 2.4 |
| F9 draw-proof | lost 1629; goals in those games avg 2.1 |
| F10 mid-price home | lost 2038: 1046 draw(s), 992 beaten |
| F11 2UP strong home | won 46 (1 only by the early payout), lost 9 |
| F12 strong home, plain | lost 10: 6 draw(s), 4 beaten |
| F13 strong home, double chance | lost 4; goals in those games avg 4.0 |
| P1 profile: BTTS yes | lost 182; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +1.9, losses -1.1 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.8, losses +1.0 |
| P4 profile: BTTS no | lost 5; goals in those games avg 4.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.7, losses +1.3 |
| B1 home favourite | lost 176 by 9 pts on average |
| B2 away underdog | lost 370 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -13.7, losses +14.9 |
| B4 main total over | total vs line (pts): wins +14.9, losses -13.7 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 28 | 12/28 | -24.7% | 43% vs 46% | 64/84 |
| A2 three favourites | 3 legs from F1 + F2 | 29 | 18/29 | +27.4% | 62% vs 43% | 74/87 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 29 | 8/29 | -51.3% | 28% vs 47% | 63/87 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 26 | 14/26 | -5.6% | 54% vs 47% | 63/78 |

Latest accas (2026-11-04):
- A2 three favourites @3.30 — LANDED (3/3): Alianza Lima v Cienciano: 1x2:home @1.45; Sporting FC v Perez Zeledon: 1x2:home @1.44; SC Internacional RS v Coritiba FC PR: 1x2:home @1.58
- A3 mixed safe @1.77 — lost (1/3): La Union Formosa v Argentino Junin: win:home @1.21; California Baptist Lancers v North Florida Ospreys: win:home @1.20; Real Cartagena FC v Deportes Quindio: dc:1x @1.22

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

