# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

6883 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 802 | 74% | +0.1% ± 2.1% | -0.0% | £100.66 | +0.2% / +0.1% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 2188 | 56% | -2.3% ± 1.9% | -0.1% | £48.70 | -2.4% / -2.3% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 1636 | 28% | -11.6% ± 3.5% | -0.7% | £-89.84 | -12.0% / -11.6% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 1127 | 27% | -13.3% ± 4.3% | -0.3% | £-49.98 | -25.4% / -11.5% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 2748 | 63% | -1.4% ± 1.5% | -0.1% | £60.46 | -0.0% / -1.7% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 1464 | 56% | -8.4% ± 2.1% | -0.9% | £-23.17 | -6.3% / -8.6% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 1788 | 48% | -15.1% ± 2.1% | -0.3% | £-170.13 | -23.3% / -14.3% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 3397 | 76% | -3.8% ± 0.9% | -0.3% | £-29.03 | +3.0% / -4.9% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 4067 | 74% | -5.6% ± 0.9% | -0.1% | £-128.51 | +0.2% / -6.5% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 2572 | 49% | -1.9% ± 2.0% | -0.4% | £52.18 | +7.9% / -3.2% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 31 | 90% | +5.7% ± 6.4% | -2.3% | £101.76 | +1.4% / +6.9% | learning (31/100 bets) |
| F12 strong home, plain | home win on F11's games | 31 | 87% | +3.0% ± 7.3% | -2.2% | £100.92 | +2.4% / +3.1% | learning (31/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 31 | 97% | +1.2% ± 3.4% | -0.9% | £100.36 | -10.1% / +4.5% | learning (31/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 195 | 57% | -5.7% ± 5.9% | +1.6% | £88.92 | -8.3% / +0.7% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 195 | 58% | -3.5% ± 5.9% | +1.2% | £93.09 | -6.4% / +3.5% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 15 | 80% | -1.5% ± 13.3% | +1.6% | £99.78 | +30.4% / -17.4% | learning (15/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 7 | 57% | +0.1% ± 35.6% | +2.0% | £100.01 | +72.0% / -28.6% | learning (7/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 109 | 68% | -6.1% ± 6.2% | -3.5% | £93.34 | -2.8% / -12.8% | no edge shown |
| B1 home favourite | home winner at 1.20–1.60 | 353 | 69% | -5.8% ± 3.4% | -0.1% | £79.63 | +3.6% / -6.6% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 401 | 39% | -4.0% ± 6.2% | -0.7% | £83.98 | +12.4% / -5.7% | no edge shown |
| B3 main total under | Under the main total line | 1036 | 48% | -11.0% ± 2.9% | -0.2% | £-14.37 | -7.6% / -11.3% | losing — avoid |
| B4 main total over | Over the main total line | 1036 | 52% | -3.7% ± 2.9% | +0.1% | £61.97 | -4.9% / -3.6% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 209: 120 draw(s), 89 beaten |
| F2 mid favourite | lost 955: 506 draw(s), 449 beaten |
| F3 home underdog | lost 1170: 433 draw(s), 737 beaten |
| F4 draw, tight game | lost 828; goals in those games avg 3.1 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.9, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.5 |
| F7 BTTS no | lost 934; goals in those games avg 3.7 |
| F8 safe double chance | lost 812; goals in those games avg 2.5 |
| F9 draw-proof | lost 1038; goals in those games avg 2.2 |
| F10 mid-price home | lost 1302: 658 draw(s), 644 beaten |
| F11 2UP strong home | won 28 (1 only by the early payout), lost 3 |
| F12 strong home, plain | lost 4: 3 draw(s), 1 beaten |
| F13 strong home, double chance | lost 1; goals in those games avg 5.0 |
| P1 profile: BTTS yes | lost 83; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +1.9, losses -1.2 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.4, losses +1.2 |
| P4 profile: BTTS no | lost 3; goals in those games avg 3.7 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.6, losses +1.5 |
| B1 home favourite | lost 110 by 8 pts on average |
| B2 away underdog | lost 246 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -13.1, losses +14.9 |
| B4 main total over | total vs line (pts): wins +14.9, losses -13.1 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 19 | 8/19 | -25.7% | 42% vs 46% | 43/57 |
| A2 three favourites | 3 legs from F1 + F2 | 19 | 10/19 | +9.1% | 53% vs 42% | 47/57 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 19 | 4/19 | -62.9% | 21% vs 47% | 39/57 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 17 | 8/17 | -17.7% | 47% vs 47% | 40/51 |

Latest accas (2026-10-25):
- A1 three safe double chances @1.82 — lost (1/3): CD Guastatoya v Deportivo Mixco: dc:1x @1.21; El Paso Locomotive FC v New Mexico United: dc:1x @1.22; Portland Timbers v Charlotte FC: dc:12 @1.23
- A2 three favourites @2.55 — lost (2/3): CD Once Caldas v Deportivo Pereira FC SA: 1x2:home @1.24; Wollongong Wolves FC v South Hobart FC: 1x2:home @1.39; CD Walter Ferretti v Rancho Santana FC: 1x2:home @1.48
- A3 mixed safe @1.77 — lost (1/3): Denver Nuggets v New Orleans Pelicans: win:home @1.20; CD Guastatoya v Deportivo Mixco: dc:1x @1.21; El Paso Locomotive FC v New Mexico United: dc:1x @1.22
- A4 three draw-proof @1.74 — LANDED (3/3): Sacramento Republic FC v Oakland Roots SC: dc:12 @1.20; Colorado Springs Switchbacks FC v FC Tulsa: dc:12 @1.21; Club Celaya FC v Cordobes FC: dc:12 @1.20

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

