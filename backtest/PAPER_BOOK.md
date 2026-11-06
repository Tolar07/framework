# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

11216 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 1280 | 73% | -0.7% ± 1.7% | -0.1% | £90.89 | +1.9% / -1.1% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 3483 | 56% | -2.2% ± 1.5% | -0.1% | £22.71 | +2.5% / -2.8% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 2629 | 29% | -9.6% ± 2.8% | -0.5% | £-153.11 | -10.2% / -9.5% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 1760 | 27% | -13.4% ± 3.5% | -0.3% | £-135.24 | -22.2% / -12.0% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 4286 | 62% | -3.5% ± 1.2% | -0.1% | £-50.89 | -3.6% / -3.5% | losing — avoid |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 2418 | 56% | -8.0% ± 1.7% | -0.9% | £-93.51 | -11.9% / -7.7% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 2820 | 48% | -14.3% ± 1.7% | -0.4% | £-304.49 | -16.5% / -14.1% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 5380 | 76% | -4.3% ± 0.7% | -0.3% | £-128.68 | +0.6% / -5.0% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 6484 | 74% | -5.7% ± 0.7% | -0.1% | £-267.16 | -0.1% / -6.5% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 4122 | 50% | -1.6% ± 1.6% | -0.2% | £35.63 | +9.8% / -3.1% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 63 | 84% | -1.4% ± 5.5% | -0.7% | £99.11 | -11.8% / +3.4% | learning (63/100 bets) |
| F12 strong home, plain | home win on F11's games | 63 | 83% | -2.2% ± 5.7% | -0.7% | £98.59 | -10.8% / +1.8% | learning (63/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 63 | 94% | -2.0% ± 3.2% | -0.4% | £98.72 | -5.7% / -0.3% | learning (63/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 432 | 56% | -7.3% ± 4.0% | +1.0% | £68.64 | -10.6% / +1.6% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 432 | 58% | -3.7% ± 4.1% | +0.5% | £83.91 | -7.1% / +5.3% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 32 | 88% | +9.2% ± 7.5% | +0.5% | £102.96 | +30.5% / +4.3% | learning (32/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 11 | 55% | +0.6% ± 29.4% | +2.0% | £100.07 | +76.7% / -27.9% | learning (11/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 227 | 64% | -12.1% ± 4.4% | -2.5% | £72.49 | -12.2% / -11.9% | losing — avoid |
| B1 home favourite | home winner at 1.20–1.60 | 580 | 67% | -8.5% ± 2.7% | -0.3% | £50.75 | -4.1% / -8.9% | losing — avoid |
| B2 away underdog | away winner at 2.00–3.50 | 644 | 39% | -2.0% ± 4.9% | -0.6% | £87.20 | +12.4% / -3.5% | no edge shown |
| B3 main total under | Under the main total line | 1776 | 49% | -9.5% ± 2.2% | -0.1% | £-68.31 | +0.4% / -10.2% | losing — avoid |
| B4 main total over | Over the main total line | 1776 | 51% | -5.1% ± 2.2% | +0.0% | £9.19 | -11.9% / -4.6% | losing — avoid |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 343: 189 draw(s), 154 beaten |
| F2 mid favourite | lost 1520: 794 draw(s), 726 beaten |
| F3 home underdog | lost 1859: 670 draw(s), 1189 beaten |
| F4 draw, tight game | lost 1293; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 1461; goals in those games avg 3.7 |
| F8 safe double chance | lost 1305; goals in those games avg 2.4 |
| F9 draw-proof | lost 1659; goals in those games avg 2.1 |
| F10 mid-price home | lost 2081: 1068 draw(s), 1013 beaten |
| F11 2UP strong home | won 53 (1 only by the early payout), lost 10 |
| F12 strong home, plain | lost 11: 7 draw(s), 4 beaten |
| F13 strong home, double chance | lost 4; goals in those games avg 4.0 |
| P1 profile: BTTS yes | lost 188; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +1.9, losses -1.1 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.8, losses +1.0 |
| P4 profile: BTTS no | lost 5; goals in those games avg 4.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.7, losses +1.3 |
| B1 home favourite | lost 192 by 8 pts on average |
| B2 away underdog | lost 391 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -13.6, losses +15.0 |
| B4 main total over | total vs line (pts): wins +15.0, losses -13.6 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 31 | 13/31 | -26.2% | 42% vs 46% | 71/93 |
| A2 three favourites | 3 legs from F1 + F2 | 31 | 20/31 | +36.1% | 65% vs 42% | 80/93 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 31 | 9/31 | -48.8% | 29% vs 47% | 69/93 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 29 | 16/29 | -3.3% | 55% vs 47% | 71/87 |

Latest accas (2026-11-06):
- A1 three safe double chances @2.03 — lost (2/3): Cruzeiro EC MG v EC Bahia BA: dc:1x @1.20; Arnett Gardens FC v Mount Pleasant FC: dc:12 @1.27; CS Herediano v Deportivo Saprissa San Jose: dc:12 @1.33
- A2 three favourites @4.55 — LANDED (3/3): CD Marathon San Pedro Sula v Platense FC Puerto Cortes: 1x2:home @1.44; Cruzeiro EC MG v EC Bahia BA: 1x2:home @1.71; Alacranes de Durango v Leones Negros UDEG: 1x2:home @1.85
- A3 mixed safe @1.83 — lost (2/3): Cruzeiro EC MG v EC Bahia BA: dc:1x @1.20; Navy Midshipmen v Delaware State Hornets: win:home @1.20; Arnett Gardens FC v Mount Pleasant FC: dc:12 @1.27
- A4 three draw-proof @1.88 — lost (2/3): CD Marathon San Pedro Sula v Platense FC Puerto Cortes: dc:12 @1.20; Cruzeiro EC MG v EC Bahia BA: dc:12 @1.23; Arnett Gardens FC v Mount Pleasant FC: dc:12 @1.27

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

