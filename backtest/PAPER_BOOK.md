# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

5402 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 635 | 74% | -0.5% ± 2.4% | -0.2% | £97.13 | -4.6% / +0.2% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 1732 | 57% | -0.9% ± 2.1% | -0.1% | £84.11 | +2.5% / -1.3% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 1296 | 29% | -10.2% ± 4.0% | -0.8% | £-32.02 | -4.5% / -11.0% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 898 | 26% | -14.9% ± 4.8% | -0.3% | £-33.88 | -43.2% / -11.0% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 2158 | 62% | -3.1% ± 1.6% | -0.1% | £33.48 | -0.2% / -3.6% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 1209 | 56% | -8.3% ± 2.4% | -0.8% | £-0.75 | -11.2% / -8.1% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 1445 | 48% | -14.9% ± 2.3% | -0.3% | £-115.53 | -24.3% / -14.1% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 2655 | 77% | -2.9% ± 1.0% | -0.3% | £24.11 | +7.4% / -4.3% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 3184 | 75% | -5.1% ± 1.0% | -0.1% | £-62.85 | +3.1% / -6.3% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 2025 | 51% | +1.0% ± 2.2% | -0.5% | £119.39 | +11.5% / -0.3% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 26 | 88% | +3.2% ± 7.5% | -2.4% | £100.83 | +1.4% / +3.8% | learning (26/100 bets) |
| F12 strong home, plain | home win on F11's games | 26 | 88% | +4.4% ± 7.6% | -2.3% | £101.15 | +2.4% / +5.2% | learning (26/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 26 | 96% | +0.5% ± 4.0% | -0.9% | £100.13 | -10.1% / +4.4% | learning (26/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 126 | 61% | +0.4% ± 7.2% | +1.2% | £100.53 | -3.1% / +8.0% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 126 | 63% | +2.0% ± 7.2% | +0.8% | £102.58 | +0.2% / +5.9% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 12 | 83% | +1.6% ± 13.8% | +1.0% | £100.19 | +27.8% / -11.5% | learning (12/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 6 | 67% | +16.8% ± 37.3% | +1.9% | £101.01 | +72.0% / -10.8% | learning (6/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 62 | 61% | -15.0% ± 8.7% | -3.4% | £90.72 | -10.4% / -21.3% | learning (62/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 276 | 68% | -6.8% ± 3.9% | -0.1% | £81.20 | +3.5% / -7.7% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 316 | 38% | -4.8% ± 7.0% | -1.4% | £84.95 | +5.6% / -5.7% | no edge shown |
| B3 main total under | Under the main total line | 800 | 47% | -13.5% ± 3.3% | -0.2% | £-8.17 | -18.6% / -13.2% | losing — avoid |
| B4 main total over | Over the main total line | 800 | 53% | -1.1% ± 3.3% | +0.1% | £90.87 | +5.8% / -1.6% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 167: 92 draw(s), 75 beaten |
| F2 mid favourite | lost 743: 400 draw(s), 343 beaten |
| F3 home underdog | lost 919: 342 draw(s), 577 beaten |
| F4 draw, tight game | lost 664; goals in those games avg 3.1 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.9, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.5 |
| F7 BTTS no | lost 753; goals in those games avg 3.7 |
| F8 safe double chance | lost 615; goals in those games avg 2.5 |
| F9 draw-proof | lost 801; goals in those games avg 2.2 |
| F10 mid-price home | lost 996: 511 draw(s), 485 beaten |
| F11 2UP strong home | won 23 (0 only by the early payout), lost 3 |
| F12 strong home, plain | lost 3: 2 draw(s), 1 beaten |
| F13 strong home, double chance | lost 1; goals in those games avg 5.0 |
| P1 profile: BTTS yes | lost 49; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +2.1, losses -1.2 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.4, losses +1.5 |
| P4 profile: BTTS no | lost 2; goals in those games avg 2.5 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.7, losses +1.5 |
| B1 home favourite | lost 89 by 8 pts on average |
| B2 away underdog | lost 196 by 14 pts on average |
| B3 main total under | total vs line (pts): wins -13.1, losses +15.1 |
| B4 main total over | total vs line (pts): wins +15.1, losses -13.1 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 16 | 8/16 | -10.0% | 50% vs 46% | 40/48 |
| A2 three favourites | 3 legs from F1 + F2 | 16 | 8/16 | +5.7% | 50% vs 41% | 39/48 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 16 | 4/16 | -53.7% | 25% vs 47% | 34/48 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 14 | 8/14 | +1.2% | 57% vs 46% | 34/42 |

Latest accas (2026-10-22):
- A1 three safe double chances @2.03 — LANDED (3/3): Oriente Petrolero v CA Nacional Potosi: dc:1x @1.24; Atlas FC v CF America: dc:12 @1.28; Club Puebla v CF Monterrey: dc:12 @1.28
- A2 three favourites @2.90 — lost (2/3): Independiente Santa Fe v Jaguares de Cordoba: 1x2:home @1.36; Deportivo Toluca FC v Club Tijuana de Caliente: 1x2:home @1.45; Barranquilla FC v America de Cali: 1x2:away @1.47
- A3 mixed safe @2.10 — LANDED (3/3): Oriente Petrolero v CA Nacional Potosi: dc:1x @1.24; Houston Rockets v Dallas Mavericks: win:home @1.32; Atlas FC v CF America: dc:12 @1.28
- A4 three draw-proof @1.94 — LANDED (3/3): Barranquilla FC v America de Cali: dc:12 @1.20; Oriente Petrolero v CA Nacional Potosi: dc:12 @1.26; Atlas FC v CF America: dc:12 @1.28

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

