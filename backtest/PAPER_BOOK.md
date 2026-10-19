# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

4839 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 579 | 74% | -0.4% ± 2.5% | -0.2% | £97.76 | -5.7% / +0.5% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 1572 | 57% | -0.3% ± 2.2% | -0.0% | £95.04 | +1.2% / -0.5% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 1176 | 29% | -10.7% ± 4.2% | -0.5% | £-25.46 | -4.0% / -11.6% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 814 | 27% | -13.4% ± 5.1% | -0.3% | £-8.93 | -42.5% / -9.8% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 1959 | 62% | -3.3% ± 1.7% | -0.2% | £35.06 | -1.0% / -3.8% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 1111 | 56% | -8.0% ± 2.5% | -0.8% | £11.30 | -6.1% / -8.1% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 1306 | 48% | -15.4% ± 2.5% | -0.3% | £-101.70 | -24.9% / -14.6% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 2418 | 77% | -2.8% ± 1.1% | -0.3% | £31.92 | +8.1% / -4.3% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 2883 | 75% | -5.2% ± 1.0% | -0.1% | £-49.73 | +3.7% / -6.4% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 1857 | 51% | +0.9% ± 2.3% | -0.4% | £117.39 | +11.0% / -0.3% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 15 | 93% | +9.2% ± 7.9% | -2.4% | £101.38 | +20.0% / +7.5% | learning (15/100 bets) |
| F12 strong home, plain | home win on F11's games | 15 | 93% | +10.3% ± 8.0% | -2.5% | £101.55 | +20.5% / +8.8% | learning (15/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 15 | 100% | +4.5% ± 0.5% | -0.9% | £100.68 | +5.5% / +4.4% | learning (15/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 92 | 59% | -3.8% ± 8.5% | +0.8% | £96.52 | -6.6% / +4.2% | learning (92/100 bets) |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 92 | 61% | -0.6% ± 8.5% | +0.1% | £99.41 | -0.6% / -0.8% | learning (92/100 bets) |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 8 | 88% | +7.5% ± 15.5% | +1.6% | £100.60 | +28.0% / -4.8% | learning (8/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 5 | 80% | +40.2% ± 35.5% | +2.8% | £102.01 | +72.0% / +19.0% | learning (5/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 48 | 60% | -16.3% ± 9.9% | -2.6% | £92.18 | -9.8% / -28.1% | learning (48/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 216 | 67% | -8.2% ± 4.5% | -0.4% | £82.39 | +4.7% / -9.3% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 255 | 38% | -4.5% ± 7.8% | -1.3% | £88.42 | +8.8% / -5.7% | no edge shown |
| B3 main total under | Under the main total line | 655 | 47% | -13.7% ± 3.6% | -0.2% | £10.33 | -26.5% / -12.9% | losing — avoid |
| B4 main total over | Over the main total line | 655 | 53% | -1.1% ± 3.6% | +0.1% | £92.83 | +13.1% / -2.0% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 152: 85 draw(s), 67 beaten |
| F2 mid favourite | lost 670: 360 draw(s), 310 beaten |
| F3 home underdog | lost 836: 312 draw(s), 524 beaten |
| F4 draw, tight game | lost 598; goals in those games avg 3.1 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.9, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.5 |
| F7 BTTS no | lost 684; goals in those games avg 3.7 |
| F8 safe double chance | lost 559; goals in those games avg 2.5 |
| F9 draw-proof | lost 727; goals in those games avg 2.2 |
| F10 mid-price home | lost 914: 470 draw(s), 444 beaten |
| F11 2UP strong home | won 14 (0 only by the early payout), lost 1 |
| F12 strong home, plain | lost 1: 1 draw(s), 0 beaten |
| F13 strong home, double chance | no loss yet |
| P1 profile: BTTS yes | lost 38; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +2.2, losses -1.2 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.5, losses +1.5 |
| P4 profile: BTTS no | lost 1; goals in those games avg 3.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.7, losses +1.6 |
| B1 home favourite | lost 72 by 8 pts on average |
| B2 away underdog | lost 158 by 14 pts on average |
| B3 main total under | total vs line (pts): wins -13.1, losses +15.5 |
| B4 main total over | total vs line (pts): wins +15.5, losses -13.1 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 12 | 7/12 | +3.1% | 58% vs 46% | 31/36 |
| A2 three favourites | 3 legs from F1 + F2 | 13 | 7/13 | +11.7% | 54% vs 42% | 32/39 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 13 | 3/13 | -59.1% | 23% vs 47% | 27/39 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 10 | 6/10 | +4.8% | 60% vs 47% | 24/30 |

Latest accas (2026-10-19):
- A2 three favourites @2.62 — lost (2/3): Rancho Santana FC v Diriangen FC Diriamba: 1x2:away @1.31; CSD Municipal v CD Guastatoya: 1x2:home @1.38; CD Marquense v CD Suchitepequez: 1x2:home @1.45
- A3 mixed safe @2.24 — lost (2/3): CF Monterrey v CF Pachuca: dc:12 @1.24; Rancho Santana FC v Diriangen FC Diriamba: 1x2:away @1.31; CSD Municipal v CD Guastatoya: 1x2:home @1.38

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

