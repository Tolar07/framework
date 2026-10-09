# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

148 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 13 | 85% | +14.4% ± 14.2% | -0.3% | £101.87 | +33.0% / +12.8% | learning (13/100 bets) |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 41 | 54% | -10.5% ± 13.2% | +2.1% | £95.70 | — / -10.5% | learning (41/100 bets) |
| F3 home underdog | home win at 2.50–5.00 | 24 | 38% | +24.2% ± 34.0% | -2.4% | £105.80 | — / +24.2% | learning (24/100 bets) |
| F4 draw, tight game | draw when the two win prices are within 25% | 10 | 30% | -13.5% ± 44.0% | -0.1% | £98.65 | — / -13.5% | learning (10/100 bets) |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 38 | 68% | +11.2% ± 12.6% | +1.1% | £104.24 | -100.0% / +14.2% | learning (38/100 bets) |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 42 | 60% | -3.1% ± 12.6% | +0.0% | £98.68 | — / -3.1% | learning (42/100 bets) |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 53 | 55% | -4.9% ± 12.1% | -0.1% | £97.39 | +78.0% / -6.5% | learning (53/100 bets) |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 49 | 80% | +0.8% ± 7.4% | +1.1% | £100.37 | — / +0.8% | learning (49/100 bets) |
| F9 draw-proof | home or away (dc 12) at 1.20–1.40 | 6 | 67% | -18.2% ± 25.9% | -0.4% | £98.91 | — / -18.2% | learning (6/100 bets) |
| F10 mid-price home | home win at 1.60–2.50 | 2 | 50% | -17.5% ± 82.5% | -15.8% | £99.65 | — / -17.5% | learning (2/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 16 | 75% | +3.4% ± 15.6% | +1.6% | £100.54 | -35.0% / +8.9% | learning (16/100 bets) |
| B2 away underdog | away winner at 2.00–3.50 | 20 | 25% | -31.5% ± 27.5% | -3.3% | £93.70 | +210.0% / -44.2% | learning (20/100 bets) |
| B3 main total under | Under the main total line | 50 | 42% | -21.8% ± 13.1% | +0.1% | £89.09 | -69.3% / -15.3% | learning (50/100 bets) |
| B4 main total over | Over the main total line | 50 | 58% | +8.8% ± 13.2% | -0.0% | £104.42 | +56.7% / +2.3% | learning (50/100 bets) |

## Why the bets won or lost

| Rule | how |
|---|---|
| F1 short favourite | lost 2: 2 draw(s), 0 beaten |
| F2 mid favourite | lost 19: 11 draw(s), 8 beaten |
| F3 home underdog | lost 15: 5 draw(s), 10 beaten |
| F4 draw, tight game | lost 7; goals in those games avg 2.9 |
| F5 over 2.5 when favoured | total vs line (goals): wins +1.7, losses -1.5 |
| F6 under 2.5 when favoured | total vs line (goals): wins -1.4, losses +1.3 |
| F7 BTTS no | lost 24; goals in those games avg 3.5 |
| F8 safe double chance | lost 10; goals in those games avg 2.5 |
| F9 draw-proof | lost 2; goals in those games avg 2.0 |
| F10 mid-price home | lost 1: 1 draw(s), 0 beaten |
| B1 home favourite | lost 4 by 8 pts on average |
| B2 away underdog | lost 15 by 11 pts on average |
| B3 main total under | total vs line (pts): wins -13.6, losses +15.5 |
| B4 main total over | total vs line (pts): wins +15.5, losses -13.6 |

## Paper accas — 3 legs a day from the strongest rules (highest fair chance, one leg a game)

| Acca | what it combines | accas | landed | £1 return | landed vs expected | legs won |
|---|---|---|---|---|---|---|
| A1 three safe double chances | 3 legs from F8 | 2 | 1/2 | -10.7% | 50% vs 45% | 5/6 |
| A2 three favourites | 3 legs from F1 + F2 | 3 | 2/3 | +145.7% | 67% vs 27% | 8/9 |
| A3 mixed safe | 3 legs from F8 + F1 + B1 | 3 | 1/3 | -39.0% | 33% vs 44% | 7/9 |
| A4 three draw-proof | 3 legs from F9 (from 2026-10-09) | 1 | 1/1 | +83.0% | 100% vs 44% | 3/3 |

Latest accas (2026-10-09):
- A2 three favourites @3.86 — LANDED (3/3): Fluminense FC RJ v Coritiba FC PR: 1x2:home @1.50; SE Palmeiras SP v EC Bahia BA: 1x2:home @1.56; CD FAS Santa Ana v Alianza FC San Salvador: 1x2:home @1.65
- A3 mixed safe @2.10 — lost (2/3): Alebrijes de Oaxaca FC v CF Correcaminos UAT: dc:12 @1.25; Los Angeles Lakers v Sacramento Kings: win:home @1.30; Antigua GFC v CSD Municipal: dc:12 @1.29
- A4 three draw-proof @1.83 — LANDED (3/3): Fluminense FC RJ v Coritiba FC PR: dc:12 @1.21; SE Palmeiras SP v EC Bahia BA: dc:12 @1.21; Alebrijes de Oaxaca FC v CF Correcaminos UAT: dc:12 @1.25

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

