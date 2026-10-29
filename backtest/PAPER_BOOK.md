# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

8368 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 984 | 73% | -1.6% ± 1.9% | -0.1% | £84.31 | +2.5% / -2.2% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 2650 | 56% | -3.2% ± 1.7% | -0.1% | £15.56 | -1.8% / -3.4% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 1989 | 29% | -9.5% ± 3.2% | -0.8% | £-88.20 | -14.9% / -8.7% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 1362 | 26% | -14.2% ± 3.9% | -0.4% | £-93.59 | -27.0% / -12.4% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 3254 | 63% | -2.1% ± 1.3% | -0.0% | £30.14 | -1.1% / -2.4% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 1778 | 56% | -8.0% ± 1.9% | -1.0% | £-41.79 | -6.2% / -8.1% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 2129 | 48% | -15.2% ± 1.9% | -0.4% | £-223.47 | -19.5% / -14.8% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 4044 | 75% | -4.6% ± 0.9% | -0.3% | £-85.86 | +0.7% / -5.4% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 4875 | 74% | -5.7% ± 0.8% | -0.1% | £-178.85 | -1.3% / -6.4% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 3109 | 49% | -3.0% ± 1.8% | -0.3% | £5.48 | +7.0% / -4.4% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 35 | 83% | -3.1% ± 7.6% | -2.1% | £98.93 | -21.1% / +3.2% | learning (35/100 bets) |
| F12 strong home, plain | home win on F11's games | 35 | 80% | -5.4% ± 8.2% | -2.0% | £98.10 | -20.3% / -0.3% | learning (35/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 35 | 91% | -4.4% ± 5.0% | -0.9% | £98.47 | -18.3% / +0.5% | learning (35/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 269 | 58% | -5.5% ± 5.0% | +1.6% | £85.23 | -9.0% / +2.3% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 269 | 57% | -5.5% ± 5.1% | +1.1% | £85.26 | -9.6% / +3.8% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 19 | 84% | +4.4% ± 10.8% | +1.6% | £100.84 | +30.5% / -7.6% | learning (19/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 10 | 50% | -7.9% ± 31.1% | +2.1% | £99.21 | +72.0% / -27.9% | learning (10/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 154 | 67% | -7.9% ± 5.3% | -3.3% | £87.83 | -5.3% / -12.1% | no edge shown |
| B1 home favourite | home winner at 1.20–1.60 | 410 | 69% | -6.0% ± 3.2% | -0.0% | £75.46 | -0.1% / -6.5% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 462 | 39% | -4.1% ± 5.8% | -0.7% | £81.25 | +17.0% / -6.2% | no edge shown |
| B3 main total under | Under the main total line | 1221 | 48% | -10.5% ± 2.7% | -0.2% | £-27.99 | -7.1% / -10.7% | losing — avoid |
| B4 main total over | Over the main total line | 1221 | 52% | -4.1% ± 2.7% | +0.0% | £49.81 | -4.8% / -4.1% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 269: 147 draw(s), 122 beaten |
| F2 mid favourite | lost 1170: 609 draw(s), 561 beaten |
| F3 home underdog | lost 1407: 511 draw(s), 896 beaten |
| F4 draw, tight game | lost 1004; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.9, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 1113; goals in those games avg 3.7 |
| F8 safe double chance | lost 993; goals in those games avg 2.5 |
| F9 draw-proof | lost 1249; goals in those games avg 2.2 |
| F10 mid-price home | lost 1593: 803 draw(s), 790 beaten |
| F11 2UP strong home | won 29 (1 only by the early payout), lost 6 |
| F12 strong home, plain | lost 7: 4 draw(s), 3 beaten |
| F13 strong home, double chance | lost 3; goals in those games avg 3.7 |
| P1 profile: BTTS yes | lost 114; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +1.8, losses -1.1 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.5, losses +1.2 |
| P4 profile: BTTS no | lost 5; goals in those games avg 4.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.6, losses +1.3 |
| B1 home favourite | lost 128 by 8 pts on average |
| B2 away underdog | lost 284 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -13.3, losses +14.9 |
| B4 main total over | total vs line (pts): wins +14.9, losses -13.3 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 23 | 10/23 | -23.4% | 43% vs 46% | 53/69 |
| A2 three favourites | 3 legs from F1 + F2 | 23 | 12/23 | +10.5% | 52% vs 42% | 57/69 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 23 | 6/23 | -54.0% | 26% vs 47% | 49/69 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 21 | 9/21 | -24.9% | 43% vs 47% | 48/63 |

Latest accas (2026-10-29):
- A1 three safe double chances @1.80 — lost (1/3): Saint Louis City SC v Portland Timbers: dc:1x @1.21; Chicago Fire v Orlando City SC: dc:12 @1.20; EC Bahia BA v Sao Paulo FC SP: dc:1x @1.24
- A2 three favourites @2.79 — LANDED (3/3): Cienciano v Atletico Grau: 1x2:home @1.32; Vancouver Whitecaps FC v San Diego FC: 1x2:home @1.45; Minnesota United FC v Sporting Kansas City: 1x2:home @1.46
- A3 mixed safe @1.80 — lost (1/3): Saint Louis City SC v Portland Timbers: dc:1x @1.21; Chicago Fire v Orlando City SC: dc:12 @1.20; EC Bahia BA v Sao Paulo FC SP: dc:1x @1.24
- A4 three draw-proof @1.74 — lost (1/3): Saint Louis City SC v Portland Timbers: dc:12 @1.21; Chicago Fire v Orlando City SC: dc:12 @1.20; CF America v Club Tijuana de Caliente: dc:12 @1.20

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

