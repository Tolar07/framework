# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

2842 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 305 | 74% | +0.8% ± 3.4% | -0.2% | £102.48 | -4.4% / +1.5% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 913 | 58% | +0.2% ± 2.8% | +0.0% | £101.62 | +9.7% / -0.7% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 674 | 28% | -13.8% ± 5.4% | -0.3% | £7.25 | -8.8% / -14.5% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 481 | 25% | -18.4% ± 6.5% | -0.2% | £11.28 | -45.6% / -14.9% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 1173 | 61% | -4.3% ± 2.2% | -0.2% | £49.55 | -0.3% / -5.0% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 679 | 57% | -6.7% ± 3.2% | -0.9% | £54.67 | -5.9% / -6.7% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 807 | 48% | -15.9% ± 3.1% | -0.1% | £-28.47 | -30.4% / -14.6% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 1422 | 77% | -3.2% ± 1.4% | -0.3% | £54.58 | +10.5% / -5.0% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 1675 | 75% | -4.3% ± 1.3% | -0.1% | £27.85 | +5.3% / -5.6% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 1080 | 50% | -0.7% ± 3.1% | -0.4% | £92.02 | +9.5% / -1.9% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 8 | 100% | +15.4% ± 2.3% | -1.4% | £101.23 | — / +15.4% | learning (8/100 bets) |
| F12 strong home, plain | home win on F11's games | 8 | 100% | +16.6% ± 2.5% | -1.6% | £101.33 | — / +16.6% | learning (8/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 8 | 100% | +3.9% ± 0.9% | -0.5% | £100.31 | — / +3.9% | learning (8/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 4 | 100% | +63.3% ± 7.7% | -1.7% | £102.53 | +52.0% / +74.5% | learning (4/100 bets) |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 4 | 100% | +73.5% ± 15.3% | -2.1% | £102.94 | +54.0% / +93.0% | learning (4/100 bets) |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 1 | 100% | +17.0% ± inf% | -0.8% | £100.17 | — / +17.0% | learning (1/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 2 | 50% | -17.5% ± 82.5% | +4.8% | £99.65 | — / -17.5% | learning (2/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 3 | 33% | -53.3% ± 46.7% | +0.5% | £98.40 | -100.0% / -30.0% | learning (3/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 140 | 68% | -6.2% ± 5.5% | -1.0% | £91.30 | +24.3% / -8.8% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 169 | 40% | +0.7% ± 9.7% | -0.6% | £101.12 | +14.3% / -0.6% | no edge shown |
| B3 main total under | Under the main total line | 420 | 47% | -13.0% ± 4.5% | -0.2% | £45.42 | -20.0% / -12.5% | losing — avoid |
| B4 main total over | Over the main total line | 420 | 53% | -1.6% ± 4.5% | +0.1% | £93.38 | +7.0% / -2.2% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 78: 39 draw(s), 39 beaten |
| F2 mid favourite | lost 384: 199 draw(s), 185 beaten |
| F3 home underdog | lost 484: 172 draw(s), 312 beaten |
| F4 draw, tight game | lost 361; goals in those games avg 3.0 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.4 |
| F7 BTTS no | lost 423; goals in those games avg 3.7 |
| F8 safe double chance | lost 334; goals in those games avg 2.4 |
| F9 draw-proof | lost 411; goals in those games avg 2.2 |
| F10 mid-price home | lost 541: 265 draw(s), 276 beaten |
| F11 2UP strong home | won 8 (0 only by the early payout), lost 0 |
| F12 strong home, plain | no loss yet |
| F13 strong home, double chance | no loss yet |
| P1 profile: BTTS yes | no loss yet |
| P2 profile: over 2.5 | total vs line (goals): wins +2.0, losses — |
| P3 profile: under 3.5 | total vs line (goals): wins -1.5, losses — |
| P4 profile: BTTS no | lost 1; goals in those games avg 3.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -0.5, losses +1.0 |
| B1 home favourite | lost 45 by 9 pts on average |
| B2 away underdog | lost 101 by 12 pts on average |
| B3 main total under | total vs line (pts): wins -12.7, losses +15.8 |
| B4 main total over | total vs line (pts): wins +15.8, losses -12.7 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 9 | 5/9 | -1.1% | 56% vs 46% | 23/27 |
| A2 three favourites | 3 legs from F1 + F2 | 9 | 6/9 | +47.6% | 67% vs 41% | 24/27 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 9 | 3/9 | -40.2% | 33% vs 47% | 19/27 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 7 | 4/7 | -0.0% | 57% vs 46% | 17/21 |

Latest accas (2026-10-15):
- A1 three safe double chances @1.85 — LANDED (3/3): Liga Deportiva Alajuelense v CS Herediano: dc:1x @1.22; Real Salt Lake v San Jose Earthquakes: dc:1x @1.23; Los Angeles Galaxy v Portland Timbers: dc:12 @1.23
- A2 three favourites @2.13 — LANDED (3/3): Managua FC v San Marcos FC: 1x2:home @1.20; Nashville SC v Sporting Kansas City: 1x2:home @1.26; Los Angeles FC v Austin FC: 1x2:home @1.41
- A3 mixed safe @1.80 — LANDED (3/3): Managua FC v San Marcos FC: 1x2:home @1.20; Liga Deportiva Alajuelense v CS Herediano: dc:1x @1.22; Real Salt Lake v San Jose Earthquakes: dc:1x @1.23
- A4 three draw-proof @1.85 — lost (2/3): FC Dallas v Seattle Sounders: dc:12 @1.22; Real Salt Lake v San Jose Earthquakes: dc:12 @1.23; Los Angeles Galaxy v Portland Timbers: dc:12 @1.23

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

