# PAPER BOOK — the system's own £1 paper bets on every game it watches

Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only with 100+ bets, a return 2 standard errors above zero and a positive CLV — then it goes to the Architect. Paper only: nothing here stakes money.

36 graded games so far.

| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 short favourite | 1X2 favourite at 1.20–1.50 | 1 | 100% | +29.0% ± inf% | +0.0% | £100.29 | — / +29.0% | learning (1/100 bets) |
| F2 mid favourite | 1X2 favourite at 1.50–2.00 | 7 | 86% | +50.7% ± 25.5% | +0.0% | £103.55 | — / +50.7% | learning (7/100 bets) |
| F3 home underdog | home win at 2.50–5.00 | 3 | 0% | -100.0% ± 0.0% | +0.0% | £97.00 | — / -100.0% | learning (3/100 bets) |
| F4 draw, tight game | draw when the two win prices are within 25% | 2 | 0% | -100.0% ± 0.0% | +0.0% | £98.00 | — / -100.0% | learning (2/100 bets) |
| F5 over 2.5 when favoured | Over 2.5 when priced shorter than Under | 5 | 60% | -0.6% ± 40.8% | +0.0% | £99.97 | — / -0.6% | learning (5/100 bets) |
| F6 under 2.5 when favoured | Under 2.5 when priced shorter than Over | 8 | 25% | -62.7% ± 24.5% | +0.0% | £94.98 | — / -62.7% | learning (8/100 bets) |
| F7 BTTS no | both teams to score — no, at 1.50–2.00 | 7 | 57% | -1.9% ± 34.8% | +0.0% | £99.87 | — / -1.9% | learning (7/100 bets) |
| F8 safe double chance | the shortest double chance at 1.20–1.40 | 11 | 100% | +25.5% ± 1.1% | +0.0% | £102.80 | — / +25.5% | learning (11/100 bets) |
| B1 home favourite | home winner at 1.20–1.60 | 8 | 88% | +19.1% ± 17.6% | +0.0% | £101.53 | — / +19.1% | learning (8/100 bets) |
| B2 away underdog | away winner at 2.00–3.50 | 6 | 17% | -53.2% ± 46.8% | +0.0% | £96.81 | — / -53.2% | learning (6/100 bets) |
| B3 main total under | Under the main total line | 16 | 62% | +16.3% ± 23.3% | +0.0% | £102.60 | — / +16.3% | learning (16/100 bets) |
| B4 main total over | Over the main total line | 16 | 38% | -28.8% ± 23.7% | +0.0% | £95.39 | — / -28.8% | learning (16/100 bets) |

**Ready to propose:** none yet — the book needs more graded games.

A rule's return is only trusted once it is large against its standard error: with £1 bets at ~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).

