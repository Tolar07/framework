# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 2219 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 316 | 11 | 3% |
| football | 1903 | 763 | 40% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 11 | 10 | 9% |
| basketball total | 11 | 11 | 0% |
| basketball win | 11 | 11 | 0% |
| football 1up | 673 | 0 | 100% |
| football 1x2 | 762 | 745 | 2% |
| football 2up | 673 | 0 | 100% |
| football btts | 748 | 690 | 8% |
| football dc | 760 | 706 | 7% |
| football ou1.5 | 735 | 699 | 5% |
| football ou2.5 | 754 | 742 | 2% |
| football ou3.5 | 746 | 715 | 4% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 2211 | 21% | -8.9% ± 3.1% | -5.6% ± 3.3% |
| football dc | 2094 | 4% | -8.0% ± 1.5% | -2.7% ± 1.7% |
| football o/u2.5 | 1466 | 9% | -5.6% ± 2.6% | -2.3% ± 2.7% |
| football o/u3.5 | 1410 | 13% | -7.3% ± 2.8% | -3.3% ± 3.0% |
| football o/u1.5 | 1380 | 8% | -4.5% ± 3.6% | +1.5% ± 4.0% |
| football btts | 1362 | 9% | -6.8% ± 2.6% | -2.9% ± 2.7% |
| basketball win | 22 | 36% | +36.7% ± 54.8% | +29.3% ± 46.4% |
| basketball total | 22 | 45% | -5.6% ± 20.6% | -6.8% ± 20.4% |
| basketball hcp | 20 | 45% | -4.7% ± 21.9% | -5.7% ± 21.7% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 102 | 25% | -23.4% ± 14.4% |
| football o/u3.5 | 15 | 53% | -1.5% ± 27.2% |
| football o/u2.5 | 14 | 43% | -0.5% ± 33.1% |
| football o/u1.5 | 12 | 42% | +17.0% ± 48.8% |
| football dc | 11 | 82% | +34.0% ± 22.7% |
| football btts | 10 | 50% | +15.6% ± 39.8% |
| basketball win | 4 | 25% | +198.5% ± 298.5% |
| basketball hcp | 2 | 50% | -0.5% ± 99.5% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
