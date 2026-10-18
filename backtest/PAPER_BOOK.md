# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

4048 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 470 | 75% | +1.0% ± 2.7% | -0.3% | £104.56 | -5.3% / +2.1% | no edge shown |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 1308 | 57% | -0.9% ± 2.4% | -0.1% | £88.51 | +2.1% / -1.2% | no edge shown |
| F3 home underdog | home win at 2.50–5.00 | 983 | 30% | -7.8% ± 4.6% | -0.8% | £23.72 | -5.7% / -8.0% | no edge shown |
| F4 draw, tight game | draw when the two win prices are within 25% | 680 | 27% | -12.0% ± 5.6% | -0.3% | £18.18 | -37.5% / -8.8% | losing — avoid |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 1679 | 61% | -4.3% ± 1.9% | -0.1% | £27.55 | -1.5% / -4.9% | losing — avoid |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 908 | 56% | -7.0% ± 2.7% | -0.9% | £36.59 | -0.2% / -7.5% | losing — avoid |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 1113 | 47% | -16.1% ± 2.7% | -0.2% | £-78.89 | -28.5% / -14.8% | losing — avoid |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 2050 | 76% | -3.7% ± 1.2% | -0.3% | £25.16 | +8.5% / -5.4% | losing — avoid |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 2417 | 75% | -4.8% ± 1.1% | -0.2% | £-16.19 | +2.7% / -5.9% | losing — avoid |
| F10 mid-price home | home win at 1.60–2.50 | 1529 | 50% | +0.0% ± 2.6% | -0.7% | £100.71 | +8.2% / -1.0% | no edge shown |
| F11 2UP strong home | home 2UP (early payout at a 2-goal lead) when the home win is 75%+ margin-free | 14 | 93% | +8.2% ± 8.4% | -2.6% | £101.15 | +20.0% / +6.2% | learning (14/100 bets) |
| F12 strong home, plain | home win on F11's games | 14 | 93% | +9.3% ± 8.5% | -2.7% | £101.30 | +20.5% / +7.4% | learning (14/100 bets) |
| F13 strong home, double chance | home or draw on F11's games | 14 | 100% | +4.4% ± 0.6% | -0.9% | £100.61 | +5.5% / +4.2% | learning (14/100 bets) |
| P1 profile: BTTS yes | BTTS yes when both teams' profiles say both score | 61 | 57% | -6.2% ± 10.5% | +1.0% | £96.23 | -12.0% / +9.0% | learning (61/100 bets) |
| P2 profile: over 2.5 | Over 2.5 on P1's games | 61 | 57% | -8.5% ± 10.4% | -0.1% | £94.82 | -11.7% / -0.1% | learning (61/100 bets) |
| P3 profile: under 3.5 | Under 3.5 when the profiles say goals are scarce | 4 | 100% | +23.0% ± 3.8% | +1.2% | £100.92 | +28.0% / +18.0% | learning (4/100 bets) |
| P4 profile: BTTS no | BTTS no when one side's profile says it won't score | 3 | 67% | +16.3% ± 58.4% | +2.3% | £100.49 | +84.0% / -17.5% | learning (3/100 bets) |
| P5 short Under 3.5 v profile | Under 3.5 at 1.20–1.50 when the profiles say both score | 31 | 65% | -10.0% ± 12.2% | -2.0% | £96.89 | -3.0% / -21.2% | learning (31/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 196 | 67% | -7.0% ± 4.7% | -0.3% | £86.29 | +4.7% / -8.2% | no edge shown |
| B2 away underdog | away winner at 2.00–3.50 | 232 | 38% | -4.9% ± 8.2% | -1.6% | £88.67 | +8.8% / -6.2% | no edge shown |
| B3 main total under | Under the main total line | 584 | 47% | -13.3% ± 3.8% | -0.2% | £22.14 | -26.5% / -12.4% | losing — avoid |
| B4 main total over | Over the main total line | 584 | 53% | -1.4% ± 3.8% | +0.1% | £91.63 | +13.1% / -2.4% | no edge shown |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 119: 63 draw(s), 56 beaten |
| F2 mid favourite | lost 560: 295 draw(s), 265 beaten |
| F3 home underdog | lost 689: 262 draw(s), 427 beaten |
| F4 draw, tight game | lost 496; goals in those games avg 3.1 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.8, losses -1.1 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.2, losses +1.5 |
| F7 BTTS no | lost 586; goals in those games avg 3.7 |
| F8 safe double chance | lost 488; goals in those games avg 2.4 |
| F9 draw-proof | lost 602; goals in those games avg 2.2 |
| F10 mid-price home | lost 759: 377 draw(s), 382 beaten |
| F11 2UP strong home | won 13 (0 only by the early payout), lost 1 |
| F12 strong home, plain | lost 1: 1 draw(s), 0 beaten |
| F13 strong home, double chance | no loss yet |
| P1 profile: BTTS yes | lost 26; goals in those games avg 1.7 |
| P2 profile: over 2.5 | total vs line (goals): wins +2.1, losses -1.2 |
| P3 profile: under 3.5 | total vs line (goals): wins -1.0, losses — |
| P4 profile: BTTS no | lost 1; goals in those games avg 3.0 |
| P5 short Under 3.5 v profile | total vs line (goals): wins -1.8, losses +1.4 |
| B1 home favourite | lost 64 by 8 pts on average |
| B2 away underdog | lost 144 by 13 pts on average |
| B3 main total under | total vs line (pts): wins -12.9, losses +15.8 |
| B4 main total over | total vs line (pts): wins +15.8, losses -12.9 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 12 | 7/12 | +3.0% | 58% vs 46% | 31/36 |
| A2 three favourites | 3 legs from F1 + F2 | 12 | 7/12 | +22.9% | 58% vs 42% | 30/36 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 12 | 4/12 | -41.2% | 33% vs 47% | 26/36 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 10 | 6/10 | +4.8% | 60% vs 46% | 25/30 |

Latest accas (2026-10-18):
- A1 three safe double chances @1.74 — LANDED (3/3): Iwaki FC v Ventforet Kofu: dc:1x @1.20; Suwon Bluewings v Hwaseong FC: dc:1x @1.20; Cancun FC v Venados  FC: dc:1x @1.21
- A2 three favourites @2.02 — LANDED (3/3): Alianza Lima v Atletico Grau: 1x2:home @1.26; Piratas Veracruz v Tepatitlan FC: 1x2:home @1.25; Managua FC v Indigenas de Matagalpa FC: 1x2:home @1.28
- A3 mixed safe @1.74 — LANDED (3/3): Iwaki FC v Ventforet Kofu: dc:1x @1.20; Suwon Bluewings v Hwaseong FC: dc:1x @1.20; Cancun FC v Venados  FC: dc:1x @1.21
- A4 three draw-proof @1.74 — lost (2/3): Austin FC v Vancouver Whitecaps FC: dc:12 @1.20; Cancun FC v Venados  FC: dc:12 @1.21; Irapuato v Zacatepec FC: dc:12 @1.20

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

