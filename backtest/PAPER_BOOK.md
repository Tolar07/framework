# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

2635 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 279 | 73% | -1.4% ± 3.6% | -0.1% | £96.11 | -3.5% / -1.1% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 867 | 57% | -1.0% ± 2.9% | +0.1% | £90.94 | +8.5% / -1.9% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 635 | 28% | -15.1% ± 5.6% | -0.6% | £4.10 | -17.2% / -14.8% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 461 | 26% | -16.3% ± 6.7% | -0.2% | £24.63 | -41.4% / -13.2% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 1105 | 61% | -4.6% ± 2.3% | -0.2% | £49.29 | -1.2% / -5.2% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 655 | 56% | -7.1% ± 3.2% | -0.8% | £53.46 | -5.9% / -7.2% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 779 | 48% | -15.5% ± 3.2% | -0.0% | £-20.52 | -29.4% / -14.2% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 1350 | 76% | -3.8% ± 1.5% | -0.3% | £48.37 | +9.3% / -5.6% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 1584 | 76% | -4.2% ± 1.4% | -0.1% | £32.75 | +3.9% / -5.3% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 1025 | 50% | -0.7% ± 3.2% | -0.4% | £93.33 | +8.6% / -1.7% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 6 | 100% | +14.7% ± 3.0% | -1.1% | £100.88 | — / +14.7% | learning (6/100 bets) |
| F12 strong home, plain | home win on F11's games | 6 | 100% | +16.0% ± 3.4% | -1.1% | £100.96 | — / +16.0% | learning (6/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 6 | 100% | +3.5% ± 1.2% | -0.3% | £100.21 | — / +3.5% | learning (6/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 1 | 100% | +73.0% ± inf% | -11.3% | £100.73 | — / +73.0% | learning (1/100 bets) |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 1 | 100% | +115.0% ± inf% | -8.5% | £101.15 | — / +115.0% | learning (1/100 bets) |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 1 | 100% | +17.0% ± inf% | -0.8% | £100.17 | — / +17.0% | learning (1/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 2 | 50% | -17.5% ± 82.5% | +4.8% | £99.65 | — / -17.5% | learning (2/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 1 | 0% | -100.0% ± inf% | +5.0% | £99.00 | — / -100.0% | learning (1/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 121 | 69% | -3.4% ± 5.9% | -0.7% | £95.84 | +24.1% / -5.7% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 150 | 39% | -4.0% ± 10.2% | -0.5% | £94.03 | +6.5% / -5.0% | no edge shown |
| B3 main total under | Under the main total line | 361 | 48% | -11.6% ± 4.9% | -0.3% | £58.04 | -18.9% / -11.1% | losing — avoid |
| B4 main total over | Over the main total line | 361 | 52% | -2.9% ± 4.9% | +0.1% | £89.37 | +5.9% / -3.5% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 76: 38 draw(s), 38 beaten |
| F2 mid favourite | lost 371: 189 draw(s), 182 beaten |
| F3 home underdog | lost 459: 168 draw(s), 291 beaten |
| F4 draw, tight game | lost 343; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 406; goals in those games avg 3.7 |
| F8 safe double chance | lost 324; goals in those games avg 2.5 |
| F9 draw-proof | lost 388; goals in those games avg 2.3 |
| F10 mid-price home | lost 514: 247 draw(s), 267 beaten |
| F11 2UP strong home | won 6 (0 only by the early payout), lost 0 |
| F12 strong home, plain | no loss yet |
| F13 strong home, double chance | no loss yet |
| P1 profile: BTTS yes | no loss yet |
| P2 profile: over 2.5 | total vs line (goals): wins +1.5, losses — |
| P3 profile: under 3.5 | total vs line (goals): wins -1.5, losses — |
| P4 profile: BTTS no | lost 1; goals in those games avg 3.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins —, losses +0.5 |
| B1 home favourite | lost 37 by 9 pts on average |
| B2 away underdog | lost 92 by 12 pts on average |
| B3 main total under | total vs line (pts): wins -12.6, losses +16.5 |
| B4 main total over | total vs line (pts): wins +16.5, losses -12.6 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 7 | 3/7 | -24.7% | 43% vs 46% | 17/21 |
| A2 three favourites | 3 legs from F1 + F2 | 7 | 4/7 | +31.1% | 57% vs 41% | 18/21 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 8 | 2/8 | -55.2% | 25% vs 45% | 16/24 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 5 | 3/5 | +4.8% | 60% vs 47% | 12/15 |

Latest accas (2026-10-14):
- A3 mixed safe @2.54 — lost (2/3): AD San Carlos v Inter San Carlos: dc:1x @1.27; Oklahoma City Thunder v Indiana Pacers: win:home @1.34; Mexico v Jamaica: 1x2:home @1.49

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

