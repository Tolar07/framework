# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

8511 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 1008 | 73% | -1.5% ± 1.9% | -0.1% | £85.04 | +2.0% / -2.0% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 2687 | 56% | -2.9% ± 1.7% | -0.1% | £22.51 | -1.3% / -3.1% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 2014 | 29% | -9.8% ± 3.2% | -0.8% | £-97.22 | -15.5% / -9.0% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 1375 | 26% | -14.3% ± 3.9% | -0.4% | £-97.16 | -27.0% / -12.6% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 3284 | 63% | -2.2% ± 1.3% | -0.0% | £28.15 | -0.8% / -2.4% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 1803 | 56% | -7.8% ± 1.9% | -0.9% | £-40.91 | -6.2% / -7.9% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 2160 | 48% | -15.0% ± 1.9% | -0.4% | £-224.66 | -19.5% / -14.6% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 4093 | 75% | -4.5% ± 0.9% | -0.3% | £-85.49 | +0.7% / -5.3% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 4933 | 74% | -5.7% ± 0.8% | -0.1% | £-182.94 | -1.3% / -6.4% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 3148 | 49% | -2.7% ± 1.8% | -0.3% | £15.63 | +6.9% / -4.0% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 36 | 83% | -2.4% ± 7.4% | -2.1% | £99.13 | -21.1% / +3.8% | learning (36/100 bets) |
| F12 strong home, plain | home win on F11's games | 36 | 81% | -4.7% ± 8.0% | -2.1% | £98.31 | -20.3% / +0.5% | learning (36/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 36 | 92% | -4.1% ± 4.9% | -0.9% | £98.53 | -18.3% / +0.7% | learning (36/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 275 | 59% | -3.9% ± 4.9% | +1.7% | £89.35 | -8.2% / +5.5% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 275 | 58% | -3.9% ± 5.0% | +1.2% | £89.32 | -8.8% / +6.8% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 20 | 85% | +5.5% ± 10.3% | +1.6% | £101.11 | +30.5% / -5.1% | learning (20/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 10 | 50% | -7.9% ± 31.1% | +2.1% | £99.21 | +72.0% / -27.9% | learning (10/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 158 | 65% | -10.2% ± 5.3% | -3.5% | £83.83 | -6.3% / -16.3% | no edge shown |
| B1 home favourite | home winner at 1.20–1.60 | 418 | 69% | -5.9% ± 3.1% | -0.1% | £75.44 | -1.4% / -6.3% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 474 | 38% | -4.8% ± 5.7% | -0.7% | £77.46 | +18.8% / -7.2% | no edge shown |
| B3 main total under | Under the main total line | 1244 | 48% | -10.8% ± 2.6% | -0.1% | £-34.16 | -4.9% / -11.2% | losing — avoid |
| B4 main total over | Over the main total line | 1244 | 52% | -3.8% ± 2.6% | +0.0% | £52.84 | -7.0% / -3.5% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 275: 149 draw(s), 126 beaten |
| F2 mid favourite | lost 1182: 616 draw(s), 566 beaten |
| F3 home underdog | lost 1427: 517 draw(s), 910 beaten |
| F4 draw, tight game | lost 1014; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.9, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 1127; goals in those games avg 3.7 |
| F8 safe double chance | lost 1003; goals in those games avg 2.5 |
| F9 draw-proof | lost 1265; goals in those games avg 2.2 |
| F10 mid-price home | lost 1608: 814 draw(s), 794 beaten |
| F11 2UP strong home | won 30 (1 only by the early payout), lost 6 |
| F12 strong home, plain | lost 7: 4 draw(s), 3 beaten |
| F13 strong home, double chance | lost 3; goals in those games avg 3.7 |
| P1 profile: BTTS yes | lost 114; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +1.9, losses -1.1 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.6, losses +1.2 |
| P4 profile: BTTS no | lost 5; goals in those games avg 4.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.6, losses +1.3 |
| B1 home favourite | lost 130 by 8 pts on average |
| B2 away underdog | lost 293 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -13.2, losses +14.9 |
| B4 main total over | total vs line (pts): wins +14.9, losses -13.2 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 23 | 10/23 | -23.4% | 43% vs 46% | 53/69 |
| A2 three favourites | 3 legs from F1 + F2 | 24 | 12/24 | +1.6% | 50% vs 43% | 59/72 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 24 | 7/24 | -48.6% | 29% vs 47% | 52/72 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 21 | 9/21 | -24.9% | 43% vs 47% | 48/63 |

Latest accas (2026-10-30):
- A2 three favourites @2.53 — lost (2/3): FBC Melgar v Comerciantes Unidos: 1x2:home @1.29; Antigua GFC v Deportivo San Pedro: 1x2:home @1.39; Atletico Nacional v Independiente Santa Fe: 1x2:home @1.41
- A3 mixed safe @2.03 — lost (1/3): CD Marquense v CD Guastatoya: dc:1x @1.22; Unan Managua v CD Walter Ferretti: dc:12 @1.29; FBC Melgar v Comerciantes Unidos: 1x2:home @1.29

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

