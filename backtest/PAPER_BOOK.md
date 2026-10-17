# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

3076 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 344 | 75% | +1.2% ± 3.2% | -0.0% | £104.06 | -0.2% / +1.4% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 974 | 58% | -0.1% ± 2.8% | -0.0% | £98.83 | +8.6% / -1.0% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 731 | 29% | -12.1% ± 5.2% | -0.3% | £11.44 | -10.8% / -12.3% | losing — avoid |
| F4 draw, tight game | draw when the two win prices are within 25% | 521 | 25% | -17.0% ± 6.3% | -0.2% | £11.23 | -43.4% / -13.6% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 1278 | 62% | -3.2% ± 2.1% | -0.1% | £58.75 | +1.5% / -4.2% | no edge shown |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 722 | 56% | -7.4% ± 3.1% | -0.9% | £46.55 | -6.0% / -7.5% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 876 | 47% | -17.2% ± 3.0% | -0.2% | £-50.52 | -33.0% / -15.6% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 1523 | 76% | -3.3% ± 1.4% | -0.3% | £50.26 | +11.1% / -5.2% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 1801 | 75% | -4.3% ± 1.3% | -0.1% | £22.71 | +4.7% / -5.5% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 1142 | 50% | -1.2% ± 3.0% | -0.6% | £86.06 | +8.2% / -2.3% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 11 | 91% | +4.9% ± 10.6% | -1.9% | £100.54 | — / +4.9% | learning (11/100 bets) |
| F12 strong home, plain | home win on F11's games | 11 | 91% | +6.0% ± 10.8% | -1.8% | £100.66 | — / +6.0% | learning (11/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 11 | 100% | +4.0% ± 0.7% | -0.6% | £100.44 | — / +4.0% | learning (11/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 16 | 62% | +1.8% ± 20.6% | -1.2% | £100.28 | +0.9% / +2.6% | learning (16/100 bets) |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 16 | 75% | +22.2% ± 18.7% | -2.0% | £103.56 | +34.2% / +10.2% | learning (16/100 bets) |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 2 | 100% | +25.5% ± 8.5% | +2.3% | £100.51 | +34.0% / +17.0% | learning (2/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 3 | 67% | +16.3% ± 58.4% | +2.3% | £100.49 | +84.0% / -17.5% | learning (3/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 8 | 50% | -30.0% ± 26.5% | +0.8% | £97.60 | -100.0% / -20.0% | learning (8/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 160 | 66% | -9.4% ± 5.3% | -1.0% | £85.03 | +17.5% / -12.1% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 192 | 42% | +4.7% ± 9.2% | -0.3% | £109.10 | +6.1% / +4.6% | no edge shown |
| B3 main total under | Under the main total line | 467 | 47% | -13.5% ± 4.3% | -0.2% | £37.16 | -17.8% / -13.1% | losing — avoid |
| B4 main total over | Over the main total line | 467 | 53% | -1.2% ± 4.3% | +0.1% | £94.36 | +4.6% / -1.7% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 87: 44 draw(s), 43 beaten |
| F2 mid favourite | lost 411: 215 draw(s), 196 beaten |
| F3 home underdog | lost 521: 187 draw(s), 334 beaten |
| F4 draw, tight game | lost 389; goals in those games avg 3.1 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.5 |
| F7 BTTS no | lost 466; goals in those games avg 3.7 |
| F8 safe double chance | lost 359; goals in those games avg 2.5 |
| F9 draw-proof | lost 442; goals in those games avg 2.2 |
| F10 mid-price home | lost 575: 280 draw(s), 295 beaten |
| F11 2UP strong home | won 10 (0 only by the early payout), lost 1 |
| F12 strong home, plain | lost 1: 1 draw(s), 0 beaten |
| F13 strong home, double chance | no loss yet |
| P1 profile: BTTS yes | lost 6; goals in those games avg 2.2 |
| P2 profile: over 2.5 | total vs line (goals): wins +2.0, losses -1.2 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.0, losses — |
| P4 profile: BTTS no | lost 1; goals in those games avg 3.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.8, losses +1.0 |
| B1 home favourite | lost 55 by 8 pts on average |
| B2 away underdog | lost 112 by 12 pts on average |
| B3 main total under | total vs line (pts): wins -12.6, losses +15.7 |
| B4 main total over | total vs line (pts): wins +15.7, losses -12.6 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 11 | 7/11 | +14.0% | 64% vs 46% | 29/33 |
| A2 three favourites | 3 legs from F1 + F2 | 11 | 6/11 | +26.6% | 55% vs 41% | 27/33 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 11 | 4/11 | -34.8% | 36% vs 47% | 24/33 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 9 | 5/9 | -2.9% | 56% vs 46% | 22/27 |

Latest accas (2026-10-17):
- A1 three safe double chances @1.92 — LANDED (3/3): Club Tijuana de Caliente v Club Puebla: dc:1x @1.24; Seongnam Ilhwa v Suwon FC: dc:x2 @1.23; JEF United Chiba v Yokohama F Marinos: dc:x2 @1.26
- A2 three favourites @2.99 — LANDED (3/3): Sanfrecce Hiroshima v Kyoto Sanga FC: 1x2:home @1.33; Kashima Antlers v V-Varen Nagasaki: 1x2:home @1.50; Geoje FC v Haman FC: 1x2:home @1.50
- A3 mixed safe @1.86 — LANDED (3/3): Saitama Broncos v Kagawa Five Arrows: win:home @1.22; Club Tijuana de Caliente v Club Puebla: dc:1x @1.24; Seongnam Ilhwa v Suwon FC: dc:x2 @1.23
- A4 three draw-proof @1.79 — lost (2/3): FC Gifu v Fukushima United FC: dc:12 @1.20; Daegu FC v Chungbuk Cheongju FC: dc:12 @1.21; Vegalta Sendai v Tokushima Vortis: dc:12 @1.23

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

