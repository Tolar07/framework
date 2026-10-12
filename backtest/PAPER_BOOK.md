# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

2247 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 235 | 72% | -1.8% ± 4.0% | -0.4% | £95.73 | +0.0% / -2.0% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 747 | 56% | -2.4% ± 3.2% | +0.2% | £81.86 | +3.8% / -3.0% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 555 | 29% | -11.3% ± 6.0% | -0.4% | £37.20 | -19.2% / -10.2% | no edge shown |
| F4 draw, tight game | draw when the two win prices are within 25% | 404 | 25% | -16.2% ± 7.2% | -0.1% | £34.49 | -45.6% / -12.6% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 955 | 60% | -6.0% ± 2.5% | -0.3% | £42.56 | -3.8% / -6.4% | losing — avoid |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 564 | 58% | -4.2% ± 3.5% | -0.7% | £76.17 | +0.2% / -4.6% | no edge shown |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 669 | 47% | -16.3% ± 3.4% | +0.1% | £-8.89 | -33.2% / -14.8% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 1172 | 76% | -3.7% ± 1.6% | -0.2% | £56.53 | +10.8% / -5.6% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 1359 | 75% | -5.1% ± 1.5% | -0.1% | £30.77 | +2.8% / -6.1% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 876 | 49% | -2.9% ± 3.4% | -0.6% | £74.25 | +4.5% / -3.7% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 5 | 100% | +15.6% ± 3.5% | +0.0% | £100.78 | — / +15.6% | learning (5/100 bets) |
| F12 strong home, plain | home win on F11's games | 5 | 100% | +17.0% ± 4.0% | +0.0% | £100.85 | — / +17.0% | learning (5/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 5 | 100% | +4.0% ± 1.3% | +0.0% | £100.20 | — / +4.0% | learning (5/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 99 | 69% | -4.0% ± 6.6% | -0.5% | £96.00 | +9.4% / -4.8% | learning (99/100 bets) |
| B2 away underdog | away winner at 2.00–3.50 | 124 | 40% | -1.8% ± 11.2% | +0.2% | £97.82 | +24.2% / -3.1% | no edge shown |
| B3 main total under | Under the main total line | 304 | 47% | -12.1% ± 5.3% | -0.3% | £63.08 | -46.4% / -10.5% | losing — avoid |
| B4 main total over | Over the main total line | 304 | 53% | -2.4% ± 5.3% | +0.1% | £92.65 | +33.7% / -4.2% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 65: 35 draw(s), 30 beaten |
| F2 mid favourite | lost 325: 165 draw(s), 160 beaten |
| F3 home underdog | lost 394: 143 draw(s), 251 beaten |
| F4 draw, tight game | lost 301; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.7, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 352; goals in those games avg 3.7 |
| F8 safe double chance | lost 280; goals in those games avg 2.4 |
| F9 draw-proof | lost 341; goals in those games avg 2.2 |
| F10 mid-price home | lost 449: 224 draw(s), 225 beaten |
| F11 2UP strong home | won 5 (0 only by the early payout), lost 0 |
| F12 strong home, plain | no loss yet |
| F13 strong home, double chance | no loss yet |
| B1 home favourite | lost 31 by 8 pts on average |
| B2 away underdog | lost 75 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -12.4, losses +17.0 |
| B4 main total over | total vs line (pts): wins +17.0, losses -12.4 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 5 | 2/5 | -29.1% | 40% vs 46% | 12/15 |
| A2 three favourites | 3 legs from F1 + F2 | 5 | 3/5 | +45.8% | 60% vs 39% | 13/15 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 6 | 1/6 | -69.5% | 17% vs 46% | 13/18 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 4 | 2/4 | -13.2% | 50% vs 46% | 9/12 |

Latest accas (2026-10-12):
- A3 mixed safe @2.06 — lost (2/3): Municipal Grecia v AD Rosario: dc:1x @1.22; Rancho Santana FC v Unan Managua: dc:12 @1.29; Denver Nuggets v Chicago Bulls: win:home @1.31
- A4 three draw-proof @1.98 — lost (1/3): Antigua GFC v CSD Coban Imperial: dc:12 @1.23; Municipal Grecia v AD Rosario: dc:12 @1.25; Rancho Santana FC v Unan Managua: dc:12 @1.29

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

