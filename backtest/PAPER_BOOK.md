# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

10384 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 1207 | 73% | -1.4% ± 1.8% | -0.2% | £83.67 | +2.1% / -1.8% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 3303 | 56% | -2.8% ± 1.5% | -0.1% | £5.98 | +1.6% / -3.4% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 2466 | 30% | -8.8% ± 2.9% | -0.6% | £-116.90 | -8.4% / -8.9% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 1670 | 27% | -13.1% ± 3.6% | -0.4% | £-118.53 | -20.1% / -12.1% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 4029 | 62% | -3.3% ± 1.2% | -0.1% | £-31.05 | -2.2% / -3.5% | losing — avoid |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 2288 | 56% | -8.7% ± 1.7% | -0.9% | £-98.80 | -10.2% / -8.6% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 2648 | 48% | -15.3% ± 1.7% | -0.4% | £-305.69 | -19.6% / -14.9% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 5075 | 76% | -4.3% ± 0.8% | -0.3% | £-118.07 | +0.4% / -5.0% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 6114 | 74% | -6.0% ± 0.7% | -0.1% | £-268.10 | -0.4% / -6.9% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 3918 | 49% | -1.9% ± 1.6% | -0.2% | £24.70 | +9.9% / -3.5% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 49 | 82% | -4.7% ± 6.6% | -1.5% | £97.68 | -16.6% / -0.0% | learning (49/100 bets) |
| F12 strong home, plain | home win on F11's games | 49 | 80% | -6.2% ± 6.9% | -1.5% | £96.96 | -15.8% / -2.4% | learning (49/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 49 | 92% | -4.1% ± 4.1% | -0.7% | £98.01 | -10.4% / -1.5% | learning (49/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 381 | 58% | -4.5% ± 4.2% | +1.1% | £83.02 | -8.4% / +5.1% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 381 | 59% | -2.0% ± 4.3% | +0.4% | £92.48 | -6.5% / +9.1% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 30 | 87% | +8.1% ± 8.0% | +0.6% | £102.44 | +30.5% / +2.5% | learning (30/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 10 | 50% | -7.9% ± 31.1% | +2.1% | £99.21 | +72.0% / -27.9% | learning (10/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 206 | 64% | -11.8% ± 4.6% | -2.7% | £75.59 | -10.4% / -14.4% | losing — avoid |
| B1 home favourite | home winner at 1.20–1.60 | 507 | 67% | -7.8% ± 2.9% | -0.3% | £60.57 | +0.6% / -8.5% | losing — avoid |
| B2 away underdog | away winner at 2.00–3.50 | 571 | 39% | -3.8% ± 5.2% | -0.5% | £78.20 | +11.4% / -5.2% | no edge shown |
| B3 main total under | Under the main total line | 1517 | 48% | -11.1% ± 2.4% | -0.1% | £-68.09 | -6.8% / -11.4% | losing — avoid |
| B4 main total over | Over the main total line | 1517 | 52% | -3.6% ± 2.4% | -0.0% | £45.54 | -4.9% / -3.5% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 329: 184 draw(s), 145 beaten |
| F2 mid favourite | lost 1454: 768 draw(s), 686 beaten |
| F3 home underdog | lost 1737: 634 draw(s), 1103 beaten |
| F4 draw, tight game | lost 1226; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 1386; goals in those games avg 3.7 |
| F8 safe double chance | lost 1232; goals in those games avg 2.4 |
| F9 draw-proof | lost 1581; goals in those games avg 2.2 |
| F10 mid-price home | lost 1985: 1024 draw(s), 961 beaten |
| F11 2UP strong home | won 40 (1 only by the early payout), lost 9 |
| F12 strong home, plain | lost 10: 6 draw(s), 4 beaten |
| F13 strong home, double chance | lost 4; goals in those games avg 4.0 |
| P1 profile: BTTS yes | lost 160; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +1.9, losses -1.1 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.8, losses +1.0 |
| P4 profile: BTTS no | lost 5; goals in those games avg 4.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.6, losses +1.3 |
| B1 home favourite | lost 165 by 9 pts on average |
| B2 away underdog | lost 350 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -13.5, losses +15.1 |
| B4 main total over | total vs line (pts): wins +15.1, losses -13.5 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 27 | 11/27 | -28.4% | 41% vs 46% | 61/81 |
| A2 three favourites | 3 legs from F1 + F2 | 27 | 15/27 | +10.8% | 56% vs 43% | 67/81 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 27 | 8/27 | -47.7% | 30% vs 47% | 59/81 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 25 | 13/25 | -8.3% | 52% vs 47% | 60/75 |

Latest accas (2026-11-02):
- A1 three safe double chances @1.83 — lost (2/3): Los Angeles FC v Minnesota United FC: dc:1x @1.21; CF Cruz Azul v Club Leon: dc:1x @1.22; Portland Timbers v Houston Dynamo: dc:1x @1.24
- A2 three favourites @2.95 — lost (2/3): Managua FC v Unan Managua: 1x2:home @1.21; Olancho FC v Platense FC Puerto Cortes: 1x2:home @1.45; Los Angeles FC v Minnesota United FC: 1x2:home @1.68
- A3 mixed safe @1.83 — lost (2/3): Los Angeles FC v Minnesota United FC: dc:1x @1.21; CF Cruz Azul v Club Leon: dc:1x @1.22; Portland Timbers v Houston Dynamo: dc:1x @1.24
- A4 three draw-proof @1.91 — LANDED (3/3): Los Angeles FC v Minnesota United FC: dc:12 @1.22; CF Cruz Azul v Club Leon: dc:12 @1.24; Portland Timbers v Houston Dynamo: dc:12 @1.26

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

