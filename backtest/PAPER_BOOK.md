# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

8055 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 934 | 73% | -1.3% ± 2.0% | -0.1% | £87.88 | +2.8% / -1.9% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 2568 | 56% | -2.9% ± 1.7% | -0.1% | £24.32 | -0.8% / -3.2% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 1924 | 29% | -9.4% ± 3.3% | -0.8% | £-80.10 | -11.7% / -9.0% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 1322 | 26% | -13.8% ± 4.0% | -0.3% | £-82.65 | -25.3% / -12.2% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 3164 | 63% | -2.1% ± 1.4% | -0.0% | £34.43 | -0.8% / -2.3% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 1736 | 56% | -8.3% ± 2.0% | -1.0% | £-43.90 | -7.7% / -8.3% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 2069 | 48% | -15.3% ± 2.0% | -0.4% | £-215.96 | -20.5% / -14.8% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 3945 | 76% | -4.5% ± 0.9% | -0.3% | £-77.14 | +1.6% / -5.4% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 4746 | 74% | -5.8% ± 0.8% | -0.1% | £-176.97 | -0.9% / -6.6% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 3030 | 49% | -2.7% ± 1.8% | -0.4% | £19.21 | +7.4% / -4.0% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 33 | 88% | +2.8% ± 6.8% | -2.3% | £100.93 | -11.3% / +7.3% | learning (33/100 bets) |
| F12 strong home, plain | home win on F11's games | 33 | 85% | +0.3% ± 7.5% | -2.2% | £100.10 | -10.4% / +3.7% | learning (33/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 33 | 94% | -1.8% ± 4.4% | -0.9% | £99.41 | -21.4% / +4.5% | learning (33/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 252 | 57% | -6.7% ± 5.1% | +1.6% | £83.24 | -8.7% / -1.6% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 252 | 58% | -5.7% ± 5.2% | +1.0% | £85.68 | -8.5% / +1.4% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 17 | 82% | +1.6% ± 11.9% | +1.4% | £100.27 | +30.4% / -10.4% | learning (17/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 10 | 50% | -7.9% ± 31.1% | +2.1% | £99.21 | +72.0% / -27.9% | learning (10/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 141 | 67% | -7.1% ± 5.5% | -3.2% | £89.97 | -4.5% / -11.7% | no edge shown |
| B1 home favourite | home winner at 1.20–1.60 | 402 | 69% | -5.9% ± 3.2% | -0.0% | £76.13 | +2.9% / -6.7% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 452 | 39% | -3.3% ± 5.8% | -0.8% | £85.24 | +13.3% / -5.0% | no edge shown |
| B3 main total under | Under the main total line | 1180 | 48% | -10.2% ± 2.7% | -0.2% | £-20.68 | -9.5% / -10.3% | losing — avoid |
| B4 main total over | Over the main total line | 1180 | 52% | -4.4% ± 2.7% | +0.0% | £47.92 | -2.5% / -4.6% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 253: 143 draw(s), 110 beaten |
| F2 mid favourite | lost 1130: 595 draw(s), 535 beaten |
| F3 home underdog | lost 1359: 499 draw(s), 860 beaten |
| F4 draw, tight game | lost 973; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.9, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 1083; goals in those games avg 3.7 |
| F8 safe double chance | lost 965; goals in those games avg 2.5 |
| F9 draw-proof | lost 1220; goals in those games avg 2.2 |
| F10 mid-price home | lost 1547: 789 draw(s), 758 beaten |
| F11 2UP strong home | won 29 (1 only by the early payout), lost 4 |
| F12 strong home, plain | lost 5: 3 draw(s), 2 beaten |
| F13 strong home, double chance | lost 2; goals in those games avg 4.0 |
| P1 profile: BTTS yes | lost 108; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +1.9, losses -1.1 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.5, losses +1.2 |
| P4 profile: BTTS no | lost 5; goals in those games avg 4.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.6, losses +1.4 |
| B1 home favourite | lost 125 by 8 pts on average |
| B2 away underdog | lost 276 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -13.2, losses +14.8 |
| B4 main total over | total vs line (pts): wins +14.8, losses -13.2 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 21 | 9/21 | -24.5% | 43% vs 46% | 49/63 |
| A2 three favourites | 3 legs from F1 + F2 | 21 | 11/21 | +7.7% | 52% vs 43% | 52/63 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 22 | 6/22 | -52.0% | 27% vs 47% | 48/66 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 19 | 8/19 | -26.2% | 42% vs 47% | 44/57 |

Latest accas (2026-10-28):
- A3 mixed safe @2.13 — lost (2/3): Penarol Mar Del Plata v San Martin Corrientes: win:home @1.26; Paisas Basktball v Caimanes Del Llano: win:home @1.29; Boyaca Chico FC v CD Junior FC: dc:12 @1.31

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

