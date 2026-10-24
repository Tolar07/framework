# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

5869 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 690 | 74% | +0.2% ± 2.3% | -0.1% | £101.32 | -4.1% / +0.9% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 1851 | 57% | -1.1% ± 2.0% | -0.1% | £79.17 | +1.5% / -1.4% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 1388 | 29% | -11.3% ± 3.9% | -0.8% | £-56.93 | -9.9% / -11.5% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 962 | 26% | -13.4% ± 4.7% | -0.3% | £-29.35 | -30.7% / -11.0% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 2322 | 62% | -2.5% ± 1.6% | -0.0% | £41.67 | -0.9% / -2.8% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 1290 | 56% | -7.9% ± 2.3% | -0.9% | £-1.79 | -12.0% / -7.6% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 1561 | 48% | -15.0% ± 2.3% | -0.4% | £-133.42 | -29.4% / -13.6% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 2860 | 76% | -3.4% ± 1.0% | -0.3% | £1.89 | +4.6% / -4.6% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 3441 | 74% | -5.7% ± 0.9% | -0.1% | £-97.55 | +0.7% / -6.7% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 2176 | 50% | -0.1% ± 2.2% | -0.5% | £97.23 | +9.7% / -1.4% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 30 | 90% | +5.2% ± 6.6% | -2.1% | £101.56 | +1.4% / +6.3% | learning (30/100 bets) |
| F12 strong home, plain | home win on F11's games | 30 | 90% | +6.4% ± 6.7% | -2.1% | £101.92 | +2.4% / +7.6% | learning (30/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 30 | 97% | +1.0% ± 3.5% | -0.9% | £100.30 | -10.1% / +4.4% | learning (30/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 142 | 62% | +1.8% ± 6.8% | +1.4% | £102.61 | -2.0% / +10.1% | no edge shown |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 142 | 61% | -1.2% ± 6.9% | +1.2% | £98.34 | -4.2% / +5.3% | no edge shown |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 13 | 85% | +4.6% ± 13.1% | +1.8% | £100.60 | +30.4% / -11.5% | learning (13/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 7 | 57% | +0.1% ± 35.6% | +2.0% | £100.01 | +72.0% / -28.6% | learning (7/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 74 | 64% | -11.8% ± 7.9% | -3.8% | £91.29 | -6.9% / -19.3% | learning (74/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 306 | 69% | -5.7% ± 3.7% | +0.1% | £82.69 | +5.3% / -6.7% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 352 | 38% | -5.2% ± 6.6% | -1.3% | £81.56 | +11.7% / -7.1% | no edge shown |
| B3 main total under | Under the main total line | 898 | 47% | -12.8% ± 3.1% | -0.2% | £-15.27 | -11.0% / -13.0% | losing — avoid |
| B4 main total over | Over the main total line | 898 | 53% | -1.9% ± 3.1% | +0.0% | £83.36 | -1.6% / -1.9% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 178: 100 draw(s), 78 beaten |
| F2 mid favourite | lost 796: 430 draw(s), 366 beaten |
| F3 home underdog | lost 991: 372 draw(s), 619 beaten |
| F4 draw, tight game | lost 708; goals in those games avg 3.1 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.9, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.5 |
| F7 BTTS no | lost 814; goals in those games avg 3.7 |
| F8 safe double chance | lost 676; goals in those games avg 2.5 |
| F9 draw-proof | lost 883; goals in those games avg 2.2 |
| F10 mid-price home | lost 1082: 554 draw(s), 528 beaten |
| F11 2UP strong home | won 27 (0 only by the early payout), lost 3 |
| F12 strong home, plain | lost 3: 2 draw(s), 1 beaten |
| F13 strong home, double chance | lost 1; goals in those games avg 5.0 |
| P1 profile: BTTS yes | lost 54; goals in those games avg 1.6 |
| P2 profile: over 2.5 | total vs line (goals): wins +2.1, losses -1.2 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.4, losses +1.5 |
| P4 profile: BTTS no | lost 3; goals in those games avg 3.7 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.7, losses +1.4 |
| B1 home favourite | lost 96 by 8 pts on average |
| B2 away underdog | lost 218 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -13.1, losses +14.9 |
| B4 main total over | total vs line (pts): wins +14.9, losses -13.1 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 18 | 9/18 | -11.3% | 50% vs 46% | 45/54 |
| A2 three favourites | 3 legs from F1 + F2 | 18 | 11/18 | +36.1% | 61% vs 41% | 46/54 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 18 | 5/18 | -50.5% | 28% vs 47% | 39/54 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 16 | 7/16 | -23.5% | 44% vs 46% | 37/48 |

Latest accas (2026-10-24):
- A1 three safe double chances @1.86 — LANDED (3/3): Club Necaxa v FC Juarez: dc:1x @1.23; Tepatitlan FC v Cancun FC: dc:12 @1.23; CD Escorpiones Belen v Sporting FC: dc:x2 @1.23
- A2 three favourites @3.77 — LANDED (3/3): Juventud Antoniana v CA Sol de America de Formosa: 1x2:home @1.51; CD Inca v Inter Santa Tecla: 1x2:away @1.55; Chapulineros de Oaxaca v Tritones Vallarta MFC: 1x2:home @1.61
- A3 mixed safe @1.86 — LANDED (3/3): Club Necaxa v FC Juarez: dc:1x @1.23; Tepatitlan FC v Cancun FC: dc:12 @1.23; CD Escorpiones Belen v Sporting FC: dc:x2 @1.23
- A4 three draw-proof @1.80 — lost (2/3): Chapulineros de Oaxaca v Tritones Vallarta MFC: dc:12 @1.21; CD Inca v Inter Santa Tecla: dc:12 @1.21; Olancho FC v CD Estrella Roja: dc:12 @1.23

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

