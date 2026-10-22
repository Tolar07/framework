# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 2422 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 393 | 24 | 6% |
| football | 2029 | 828 | 41% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 24 | 23 | 4% |
| basketball lines | 5 | 0 | 100% |
| basketball total | 24 | 24 | 0% |
| basketball win | 24 | 23 | 4% |
| football 1up | 734 | 0 | 100% |
| football 1x2 | 827 | 810 | 2% |
| football 2up | 734 | 0 | 100% |
| football btts | 812 | 754 | 7% |
| football dc | 825 | 771 | 7% |
| football ladder | 9 | 0 | 100% |
| football ou1.5 | 799 | 763 | 5% |
| football ou2.5 | 819 | 807 | 1% |
| football ou3.5 | 809 | 778 | 4% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 2403 | 21% | -8.9% ± 3.0% | -5.6% ± 3.2% |
| football dc | 2286 | 5% | -8.0% ± 1.5% | -2.6% ± 1.6% |
| football o/u2.5 | 1594 | 9% | -5.9% ± 2.5% | -2.6% ± 2.6% |
| football o/u3.5 | 1534 | 12% | -6.9% ± 2.7% | -2.9% ± 2.9% |
| football o/u1.5 | 1506 | 7% | -5.4% ± 3.4% | +0.3% ± 3.8% |
| football btts | 1488 | 9% | -6.9% ± 2.5% | -3.0% ± 2.6% |
| basketball total | 48 | 48% | -4.7% ± 13.9% | -6.7% ± 13.6% |
| basketball win | 46 | 46% | +16.4% ± 29.1% | +10.5% ± 25.1% |
| basketball hcp | 46 | 54% | -3.7% ± 14.4% | -7.0% ± 13.9% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 111 | 27% | -19.8% ± 13.9% |
| football o/u3.5 | 15 | 53% | -1.5% ± 27.2% |
| football o/u2.5 | 14 | 43% | -0.5% ± 33.1% |
| football o/u1.5 | 12 | 42% | +17.0% ± 48.8% |
| football dc | 11 | 82% | +34.0% ± 22.7% |
| football btts | 10 | 50% | +15.6% ± 39.8% |
| basketball win | 8 | 38% | +133.8% ± 150.3% |
| basketball hcp | 4 | 75% | +50.2% ± 50.1% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
