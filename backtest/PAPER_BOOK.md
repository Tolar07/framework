# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

117 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 9 | 78% | +3.9% ± 19.8% | -0.9% | £100.35 | — / +3.9% | learning (9/100 bets) |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 32 | 53% | -9.9% ± 15.3% | +2.4% | £96.82 | — / -9.9% | learning (32/100 bets) |
| F3 home underdog | home win at 2.50–5.00 | 19 | 42% | +38.9% ± 39.2% | -4.5% | £107.40 | — / +38.9% | learning (19/100 bets) |
| F4 draw, tight game | draw when the two win prices are within 25% | 8 | 12% | -63.7% ± 36.2% | +0.7% | £94.90 | — / -63.7% | learning (8/100 bets) |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 29 | 72% | +15.5% ± 13.7% | +0.6% | £104.50 | — / +15.5% | learning (29/100 bets) |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 34 | 56% | -9.9% ± 14.1% | +0.2% | £96.64 | — / -9.9% | learning (34/100 bets) |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 41 | 56% | -2.1% ± 13.8% | +0.3% | £99.15 | — / -2.1% | learning (41/100 bets) |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 41 | 83% | +5.1% ± 7.6% | +1.3% | £102.11 | — / +5.1% | learning (41/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 11 | 82% | +11.5% ± 17.0% | +0.6% | £101.26 | — / +11.5% | learning (11/100 bets) |
| B2 away underdog | away winner at 2.00–3.50 | 14 | 14% | -61.2% ± 26.4% | -1.8% | £91.43 | — / -61.2% | learning (14/100 bets) |
| B3 main total under | Under the main total line | 38 | 45% | -16.8% ± 15.2% | -0.0% | £93.62 | -100.0% / -7.0% | learning (38/100 bets) |
| B4 main total over | Over the main total line | 38 | 55% | +3.8% ± 15.4% | +0.1% | £101.46 | +87.5% / -6.0% | learning (38/100 bets) |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 2: 2 draw(s), 0 beaten |
| F2 mid favourite | lost 15: 8 draw(s), 7 beaten |
| F3 home underdog | lost 11: 2 draw(s), 9 beaten |
| F4 draw, tight game | lost 7; goals in those games avg 2.9 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.5 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.4, losses +1.4 |
| F7 BTTS no | lost 18; goals in those games avg 3.7 |
| F8 safe double chance | lost 7; goals in those games avg 2.4 |
| B1 home favourite | lost 2 by 10 pts on average |
| B2 away underdog | lost 12 by 11 pts on average |
| B3 main total under | total vs line (pts): wins -15.4, losses +13.2 |
| B4 main total over | total vs line (pts): wins +13.2, losses -15.4 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 2 | 1/2 | -10.7% | 50% vs 45% | 5/6 |
| A2 three favourites | 3 legs from F1 + F2 | 2 | 1/2 | +75.4% | 50% vs 29% | 5/6 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 2 | 1/2 | -8.6% | 50% vs 46% | 5/6 |

Latest accas (2026-10-08):
- A1 three safe double chances @1.76 — lost (2/3): Cruzeiro EC MG v Sao Paulo FC SP: dc:1x @1.21; MS Tira v Ironi Nesher: dc:x2 @1.20; Hapoel Herzelia FC v Hapoel Mahane Yehuda: dc:1x @1.21
- A2 three favourites @2.10 — lost (2/3): Shabab Al Ahli Dubai v Dubai United FC: 1x2:home @1.26; Al Ain FC v Ittihad Kalba FC: 1x2:home @1.27; Hapoel Karmiel FC v Hapoel Tirat Hacarmel: 1x2:home @1.31
- A3 mixed safe @1.76 — lost (2/3): Cruzeiro EC MG v Sao Paulo FC SP: dc:1x @1.21; MS Tira v Ironi Nesher: dc:x2 @1.20; Hapoel Herzelia FC v Hapoel Mahane Yehuda: dc:1x @1.21

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

