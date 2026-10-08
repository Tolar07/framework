# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

47 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 2 | 100% | +29.5% ± 0.5% | +0.0% | £100.59 | — / +29.5% | learning (2/100 bets) |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 10 | 80% | +38.6% ± 23.4% | +2.0% | £103.86 | — / +38.6% | learning (10/100 bets) |
| F3 home underdog | home win at 2.50–5.00 | 4 | 0% | -100.0% ± 0.0% | -1.4% | £96.00 | — / -100.0% | learning (4/100 bets) |
| F4 draw, tight game | draw when the two win prices are within 25% | 3 | 0% | -100.0% ± 0.0% | +1.0% | £97.00 | — / -100.0% | learning (3/100 bets) |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 9 | 56% | -10.3% ± 28.5% | +0.5% | £99.07 | — / -10.3% | learning (9/100 bets) |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 9 | 33% | -46.8% ± 26.9% | +0.0% | £95.79 | — / -46.8% | learning (9/100 bets) |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 10 | 60% | +4.8% ± 28.6% | -0.2% | £100.48 | — / +4.8% | learning (10/100 bets) |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 13 | 100% | +25.3% ± 1.0% | -0.1% | £103.29 | — / +25.3% | learning (13/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 8 | 88% | +19.1% ± 17.6% | +0.0% | £101.53 | — / +19.1% | learning (8/100 bets) |
| B2 away underdog | away winner at 2.00–3.50 | 7 | 14% | -59.9% ± 40.1% | +0.0% | £95.81 | — / -59.9% | learning (7/100 bets) |
| B3 main total under | Under the main total line | 22 | 45% | -15.5% ± 20.2% | -0.2% | £96.60 | -100.0% / +3.3% | learning (22/100 bets) |
| B4 main total over | Over the main total line | 22 | 55% | +3.0% ± 20.5% | +0.1% | £100.65 | +87.5% / -15.8% | learning (22/100 bets) |

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

