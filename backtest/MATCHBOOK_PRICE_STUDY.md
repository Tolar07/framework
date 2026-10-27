# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 6249 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 1153 | 66 | 6% |
| football | 5096 | 1821 | 36% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 66 | 65 | 2% |
| basketball lines | 39 | 0 | 100% |
| basketball total | 66 | 64 | 3% |
| basketball win | 66 | 65 | 2% |
| football 1up | 1617 | 0 | 100% |
| football 1x2 | 1820 | 1777 | 2% |
| football 2up | 1617 | 0 | 100% |
| football btts | 1788 | 1657 | 7% |
| football dc | 1814 | 1681 | 7% |
| football ladder | 833 | 0 | 100% |
| football ou1.5 | 1729 | 1657 | 4% |
| football ou2.5 | 1804 | 1768 | 2% |
| football ou3.5 | 1769 | 1708 | 3% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 4836 | 20% | -8.0% ± 2.1% | -4.7% ± 2.3% |
| football dc | 4587 | 5% | -7.8% ± 1.0% | -2.4% ± 1.2% |
| football o/u2.5 | 3204 | 9% | -6.5% ± 1.7% | -3.4% ± 1.8% |
| football o/u3.5 | 3102 | 12% | -7.2% ± 1.9% | -3.4% ± 2.0% |
| football o/u1.5 | 3024 | 8% | -9.1% ± 2.3% | -4.0% ± 2.5% |
| football btts | 3012 | 9% | -8.0% ± 1.7% | -4.2% ± 1.8% |
| basketball win | 124 | 32% | -0.7% ± 12.8% | -2.0% ± 11.6% |
| basketball hcp | 124 | 35% | -4.3% ± 8.6% | -4.5% ± 8.6% |
| basketball total | 122 | 29% | -4.3% ± 8.7% | -4.2% ± 8.7% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 207 | 34% | +1.9% ± 11.8% |
| football o/u3.5 | 32 | 50% | -11.9% ± 16.9% |
| football o/u2.5 | 29 | 45% | +2.9% ± 22.9% |
| football o/u1.5 | 25 | 24% | -31.0% ± 27.8% |
| football dc | 16 | 81% | +29.8% ± 18.0% |
| basketball win | 15 | 47% | +71.3% ± 81.3% |
| football btts | 14 | 36% | -17.4% ± 31.5% |
| basketball hcp | 8 | 75% | +47.4% ± 32.3% |
| basketball total | 1 | 0% | -100.0% ± 0.0% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
