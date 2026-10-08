# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

54 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 2 | 100% | +29.5% ± 0.5% | +0.0% | £100.59 | — / +29.5% | learning (2/100 bets) |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 11 | 73% | +26.0% ± 24.7% | +1.8% | £102.86 | — / +26.0% | learning (11/100 bets) |
| F3 home underdog | home win at 2.50–5.00 | 5 | 20% | -38.0% ± 62.0% | -1.1% | £98.10 | — / -38.0% | learning (5/100 bets) |
| F4 draw, tight game | draw when the two win prices are within 25% | 3 | 0% | -100.0% ± 0.0% | +1.0% | £97.00 | — / -100.0% | learning (3/100 bets) |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 10 | 60% | -4.3% ± 26.2% | +0.4% | £99.57 | — / -4.3% | learning (10/100 bets) |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 9 | 33% | -46.8% ± 26.9% | +0.0% | £95.79 | — / -46.8% | learning (9/100 bets) |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 10 | 60% | +4.8% ± 28.6% | -0.2% | £100.48 | — / +4.8% | learning (10/100 bets) |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 14 | 100% | +25.2% ± 0.9% | -0.1% | £103.53 | — / +25.2% | learning (14/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 8 | 88% | +19.1% ± 17.6% | +0.0% | £101.53 | — / +19.1% | learning (8/100 bets) |
| B2 away underdog | away winner at 2.00–3.50 | 9 | 11% | -68.8% ± 31.2% | -1.3% | £93.81 | — / -68.8% | learning (9/100 bets) |
| B3 main total under | Under the main total line | 28 | 46% | -13.3% ± 17.9% | -0.0% | £96.27 | -100.0% / +1.1% | learning (28/100 bets) |
| B4 main total over | Over the main total line | 28 | 54% | +0.9% ± 18.1% | +0.0% | £100.24 | +87.5% / -13.6% | learning (28/100 bets) |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | no loss yet |
| F2 mid favourite | lost 3: 1 draw(s), 2 beaten |
| F3 home underdog | lost 4: 0 draw(s), 4 beaten |
| F4 draw, tight game | lost 3; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.7, losses -1.5 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.3 |
| F7 BTTS no | lost 4; goals in those games avg 4.0 |
| F8 safe double chance | no loss yet |
| B1 home favourite | lost 1 by 2 pts on average |
| B2 away underdog | lost 8 by 9 pts on average |
| B3 main total under | total vs line (pts): wins -15.4, losses +13.6 |
| B4 main total over | total vs line (pts): wins +13.6, losses -15.4 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 2 | 2/2 | +85.3% | 100% vs 43% | 6/6 |
| A2 three favourites | 3 legs from F1 + F2 | 2 | 1/2 | +75.4% | 50% vs 23% | 5/6 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 2 | 2/2 | +87.5% | 100% vs 44% | 6/6 |

Latest accas (2026-10-08):
- A1 three safe double chances @1.92 — LANDED (3/3): Cruzeiro EC MG v Sao Paulo FC SP: dc:1x @1.21; Slovenia v Serbia: dc:12 @1.24; Corpus Christi FC v Fort Wayne FC: dc:12 @1.28
- A2 three favourites @3.06 — lost (2/3): Guabira Montero v The Strongest: 1x2:home @1.30; Oriente Petrolero v FC Universitario de Vinto: 1x2:home @1.52; Unan Managua v Real Esteli FC: 1x2:away @1.55
- A3 mixed safe @1.92 — LANDED (3/3): Cruzeiro EC MG v Sao Paulo FC SP: dc:1x @1.21; Slovenia v Serbia: dc:12 @1.24; Corpus Christi FC v Fort Wayne FC: dc:12 @1.28

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

