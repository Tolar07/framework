# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

10663 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 1226 | 73% | -1.3% ± 1.7% | -0.1% | £83.93 | +2.4% / -1.8% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 3354 | 56% | -2.6% ± 1.5% | -0.2% | £12.24 | +2.3% / -3.2% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 2517 | 30% | -9.1% ± 2.9% | -0.6% | £-128.97 | -7.8% / -9.3% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 1711 | 27% | -13.3% ± 3.5% | -0.4% | £-127.68 | -21.1% / -12.2% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 4095 | 62% | -3.3% ± 1.2% | -0.1% | £-34.18 | -2.3% / -3.5% | losing — avoid |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 2348 | 56% | -8.5% ± 1.7% | -0.9% | £-98.58 | -13.2% / -8.1% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 2713 | 48% | -15.0% ± 1.7% | -0.4% | £-308.29 | -18.0% / -14.8% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 5176 | 76% | -4.3% ± 0.8% | -0.3% | £-122.08 | +0.7% / -5.1% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 6232 | 74% | -5.9% ± 0.7% | -0.1% | £-268.28 | +0.0% / -6.8% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 3988 | 50% | -1.5% ± 1.6% | -0.2% | £39.56 | +10.3% / -3.1% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 51 | 82% | -3.9% ± 6.3% | -1.4% | £98.03 | -16.6% / +0.9% | learning (51/100 bets) |
| F12 strong home, plain | home win on F11's games | 51 | 80% | -5.2% ± 6.7% | -1.4% | £97.33 | -15.8% / -1.2% | learning (51/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 51 | 92% | -3.7% ± 4.0% | -0.7% | £98.10 | -10.4% / -1.2% | learning (51/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 394 | 57% | -5.4% ± 4.2% | +1.1% | £78.55 | -8.9% / +3.2% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 394 | 59% | -2.0% ± 4.3% | +0.4% | £92.22 | -5.6% / +7.1% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 31 | 87% | +9.0% ± 7.8% | +0.5% | £102.78 | +30.5% / +3.8% | learning (31/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 10 | 50% | -7.9% ± 31.1% | +2.1% | £99.21 | +72.0% / -27.9% | learning (10/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 213 | 63% | -12.9% ± 4.6% | -2.7% | £72.57 | -12.3% / -13.9% | losing — avoid |
| B1 home favourite | home winner at 1.20–1.60 | 529 | 67% | -8.0% ± 2.8% | -0.4% | £57.46 | -3.2% / -8.5% | losing — avoid |
| B2 away underdog | away winner at 2.00–3.50 | 594 | 39% | -2.6% ± 5.1% | -0.4% | £84.62 | +17.4% / -4.7% | no edge shown |
| B3 main total under | Under the main total line | 1630 | 48% | -10.7% ± 2.3% | -0.1% | £-74.30 | -1.5% / -11.4% | losing — avoid |
| B4 main total over | Over the main total line | 1630 | 52% | -3.9% ± 2.3% | -0.0% | £36.41 | -10.0% / -3.5% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 334: 186 draw(s), 148 beaten |
| F2 mid favourite | lost 1472: 777 draw(s), 695 beaten |
| F3 home underdog | lost 1774: 650 draw(s), 1124 beaten |
| F4 draw, tight game | lost 1257; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 1416; goals in those games avg 3.7 |
| F8 safe double chance | lost 1257; goals in those games avg 2.4 |
| F9 draw-proof | lost 1607; goals in those games avg 2.1 |
| F10 mid-price home | lost 2013: 1036 draw(s), 977 beaten |
| F11 2UP strong home | won 42 (1 only by the early payout), lost 9 |
| F12 strong home, plain | lost 10: 6 draw(s), 4 beaten |
| F13 strong home, double chance | lost 4; goals in those games avg 4.0 |
| P1 profile: BTTS yes | lost 168; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +1.9, losses -1.1 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.8, losses +1.0 |
| P4 profile: BTTS no | lost 5; goals in those games avg 4.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.6, losses +1.3 |
| B1 home favourite | lost 173 by 9 pts on average |
| B2 away underdog | lost 361 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -13.7, losses +15.0 |
| B4 main total over | total vs line (pts): wins +15.0, losses -13.7 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 28 | 11/28 | -30.9% | 39% vs 46% | 63/84 |
| A2 three favourites | 3 legs from F1 + F2 | 27 | 16/27 | +17.3% | 59% vs 43% | 68/81 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 28 | 8/28 | -49.6% | 29% vs 47% | 61/84 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 26 | 13/26 | -12.4% | 50% vs 46% | 62/78 |

Latest accas (2026-11-03):
- A1 three safe double chances @2.08 — lost (2/3): CD Suchitepequez v CD Malacateco: dc:1x @1.23; CA Bucaramanga v Atletico Nacional: dc:12 @1.30; Waterhouse FC v Cavalier FC: dc:12 @1.30
- A3 mixed safe @1.81 — lost (1/3): Dallas Mavericks v Sacramento Kings: win:home @1.25; UC Davis Aggies v North Alabama Lions: win:home @1.20; San Francisco Dons v Radford Highlanders: win:home @1.21
- A4 three draw-proof @2.18 — lost (2/3): CD Suchitepequez v CD Malacateco: dc:12 @1.29; CA Bucaramanga v Atletico Nacional: dc:12 @1.30; Waterhouse FC v Cavalier FC: dc:12 @1.30

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

