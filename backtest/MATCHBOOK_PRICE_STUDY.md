# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 6018 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 1098 | 60 | 5% |
| football | 4920 | 1750 | 36% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 60 | 59 | 2% |
| basketball lines | 34 | 0 | 100% |
| basketball total | 60 | 58 | 3% |
| basketball win | 60 | 59 | 2% |
| football 1up | 1556 | 0 | 100% |
| football 1x2 | 1749 | 1708 | 2% |
| football 2up | 1556 | 0 | 100% |
| football btts | 1718 | 1590 | 7% |
| football dc | 1743 | 1613 | 7% |
| football ladder | 785 | 0 | 100% |
| football ou1.5 | 1659 | 1588 | 4% |
| football ou2.5 | 1733 | 1699 | 2% |
| football ou3.5 | 1702 | 1642 | 4% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 4695 | 21% | -7.7% ± 2.2% | -4.4% ± 2.3% |
| football dc | 4449 | 5% | -7.7% ± 1.1% | -2.3% ± 1.2% |
| football o/u2.5 | 3112 | 9% | -6.4% ± 1.8% | -3.3% ± 1.8% |
| football o/u3.5 | 3014 | 12% | -7.0% ± 1.9% | -3.2% ± 2.1% |
| football o/u1.5 | 2932 | 8% | -8.8% ± 2.3% | -3.7% ± 2.6% |
| football btts | 2924 | 9% | -8.0% ± 1.8% | -4.1% ± 1.8% |
| basketball win | 114 | 32% | -1.2% ± 13.5% | -2.7% ± 12.2% |
| basketball hcp | 114 | 37% | -4.3% ± 9.0% | -4.8% ± 9.0% |
| basketball total | 112 | 29% | -4.3% ± 9.1% | -4.4% ± 9.1% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 203 | 33% | +0.5% ± 11.9% |
| football o/u3.5 | 30 | 47% | -19.6% ± 17.1% |
| football o/u2.5 | 28 | 43% | +1.8% ± 23.7% |
| football o/u1.5 | 25 | 24% | -31.0% ± 27.8% |
| football dc | 16 | 81% | +29.8% ± 18.0% |
| basketball win | 13 | 38% | +72.6% ± 94.3% |
| football btts | 12 | 42% | -3.7% ± 35.4% |
| basketball hcp | 6 | 83% | +63.3% ± 32.8% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
