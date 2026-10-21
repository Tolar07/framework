# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

5199 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 611 | 74% | -0.0% ± 2.4% | -0.2% | £99.89 | -4.7% / +0.7% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 1684 | 57% | -1.1% ± 2.1% | +0.0% | £82.30 | +1.4% / -1.3% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 1267 | 29% | -10.6% ± 4.0% | -0.8% | £-34.50 | -7.1% / -11.1% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 881 | 26% | -14.6% ± 4.9% | -0.3% | £-29.00 | -42.6% / -10.8% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 2081 | 62% | -3.9% ± 1.7% | -0.1% | £18.85 | -1.0% / -4.5% | losing — avoid |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 1182 | 56% | -8.5% ± 2.4% | -0.9% | £-0.54 | -10.1% / -8.4% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 1402 | 48% | -15.5% ± 2.4% | -0.3% | £-117.52 | -24.0% / -14.7% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 2581 | 77% | -2.8% ± 1.1% | -0.3% | £26.50 | +7.4% / -4.3% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 3096 | 75% | -5.1% ± 1.0% | -0.1% | £-59.29 | +2.9% / -6.3% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 1966 | 51% | +0.5% ± 2.3% | -0.5% | £110.78 | +10.7% / -0.7% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 20 | 95% | +9.8% ± 5.9% | -2.4% | £101.96 | +15.5% / +8.4% | learning (20/100 bets) |
| F12 strong home, plain | home win on F11's games | 20 | 95% | +10.9% ± 6.0% | -2.2% | £102.19 | +16.2% / +9.6% | learning (20/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 20 | 100% | +4.1% ± 0.5% | -0.8% | £100.82 | +4.0% / +4.1% | learning (20/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 110 | 58% | -4.3% ± 7.8% | +0.9% | £95.22 | -5.8% / -0.7% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 110 | 60% | -2.4% ± 7.8% | +0.4% | £97.38 | -3.6% / +0.6% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 12 | 83% | +1.6% ± 13.8% | +1.0% | £100.19 | +27.8% / -11.5% | learning (12/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 6 | 67% | +16.8% ± 37.3% | +1.9% | £101.01 | +72.0% / -10.8% | learning (6/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 54 | 63% | -12.9% ± 9.2% | -3.2% | £93.05 | -6.7% / -22.6% | learning (54/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 248 | 67% | -7.3% ± 4.1% | -0.2% | £81.97 | +4.7% / -8.2% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 290 | 38% | -5.5% ± 7.3% | -1.4% | £84.12 | +8.4% / -6.6% | no edge shown |
| B3 main total under | Under the main total line | 727 | 46% | -14.3% ± 3.4% | -0.2% | £-3.81 | -25.4% / -13.6% | losing — avoid |
| B4 main total over | Over the main total line | 727 | 54% | -0.4% ± 3.4% | +0.1% | £97.10 | +12.2% / -1.1% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 159: 88 draw(s), 71 beaten |
| F2 mid favourite | lost 724: 390 draw(s), 334 beaten |
| F3 home underdog | lost 900: 334 draw(s), 566 beaten |
| F4 draw, tight game | lost 651; goals in those games avg 3.1 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.9, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.5 |
| F7 BTTS no | lost 735; goals in those games avg 3.7 |
| F8 safe double chance | lost 598; goals in those games avg 2.5 |
| F9 draw-proof | lost 780; goals in those games avg 2.2 |
| F10 mid-price home | lost 972: 497 draw(s), 475 beaten |
| F11 2UP strong home | won 19 (0 only by the early payout), lost 1 |
| F12 strong home, plain | lost 1: 1 draw(s), 0 beaten |
| F13 strong home, double chance | no loss yet |
| P1 profile: BTTS yes | lost 46; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +2.2, losses -1.2 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.4, losses +1.5 |
| P4 profile: BTTS no | lost 2; goals in those games avg 2.5 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.7, losses +1.5 |
| B1 home favourite | lost 81 by 8 pts on average |
| B2 away underdog | lost 181 by 14 pts on average |
| B3 main total under | total vs line (pts): wins -13.1, losses +15.6 |
| B4 main total over | total vs line (pts): wins +15.6, losses -13.1 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 15 | 7/15 | -17.5% | 47% vs 46% | 37/45 |
| A2 three favourites | 3 legs from F1 + F2 | 15 | 8/15 | +12.7% | 53% vs 40% | 36/45 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 15 | 3/15 | -64.6% | 20% vs 47% | 31/45 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 13 | 6/13 | -19.4% | 46% vs 46% | 30/39 |

Latest accas (2026-10-21):
- A1 three safe double chances @2.00 — lost (2/3): Tigres UANL v Club Leon: dc:1x @1.23; Fukushima United FC v Giravanz Kitakyushu: dc:12 @1.27; Montedio Yamagata v Hokkaido Consadole Sapporo: dc:12 @1.28
- A2 three favourites @4.15 — lost (1/3): CD Guadalajara v Club Necaxa: 1x2:home @1.35; Millonarios FC v CD Once Caldas: 1x2:home @1.67; Tigres UANL v Club Leon: 1x2:home @1.84
- A3 mixed safe @2.00 — lost (2/3): Tigres UANL v Club Leon: dc:1x @1.23; Fukushima United FC v Giravanz Kitakyushu: dc:12 @1.27; Montedio Yamagata v Hokkaido Consadole Sapporo: dc:12 @1.28
- A4 three draw-proof @2.02 — lost (2/3): Millonarios FC v CD Once Caldas: dc:12 @1.25; Tigres UANL v Club Leon: dc:12 @1.27; Fukushima United FC v Giravanz Kitakyushu: dc:12 @1.27

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

