# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 6618 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 1234 | 77 | 6% |
| football | 5384 | 1950 | 36% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 77 | 76 | 1% |
| basketball lines | 50 | 0 | 100% |
| basketball total | 77 | 75 | 3% |
| basketball win | 77 | 76 | 1% |
| football 1up | 1728 | 0 | 100% |
| football 1x2 | 1949 | 1906 | 2% |
| football 2up | 1728 | 0 | 100% |
| football btts | 1905 | 1773 | 7% |
| football dc | 1943 | 1804 | 7% |
| football ladder | 941 | 0 | 100% |
| football ou1.5 | 1840 | 1768 | 4% |
| football ou2.5 | 1930 | 1893 | 2% |
| football ou3.5 | 1889 | 1828 | 3% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 5121 | 20% | -8.3% ± 2.1% | -4.9% ± 2.2% |
| football dc | 4857 | 5% | -7.9% ± 1.0% | -2.5% ± 1.1% |
| football o/u2.5 | 3390 | 9% | -6.7% ± 1.7% | -3.5% ± 1.7% |
| football o/u3.5 | 3286 | 12% | -7.4% ± 1.8% | -3.7% ± 2.0% |
| football o/u1.5 | 3196 | 8% | -9.1% ± 2.2% | -4.0% ± 2.5% |
| football btts | 3192 | 9% | -8.0% ± 1.7% | -4.2% ± 1.8% |
| basketball win | 146 | 34% | +0.1% ± 11.6% | -1.0% ± 10.7% |
| basketball hcp | 146 | 38% | -4.3% ± 7.9% | -4.5% ± 7.9% |
| basketball total | 144 | 32% | -4.4% ± 8.0% | -4.2% ± 8.0% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 224 | 33% | -1.1% ± 11.1% |
| football o/u3.5 | 35 | 49% | -13.9% ± 16.1% |
| football o/u2.5 | 30 | 43% | -0.5% ± 22.4% |
| football o/u1.5 | 26 | 23% | -33.7% ± 26.8% |
| football dc | 20 | 80% | +25.0% ± 16.2% |
| basketball win | 19 | 47% | +67.2% ± 66.9% |
| football btts | 15 | 40% | -10.3% ± 30.2% |
| basketball hcp | 10 | 60% | +17.9% ± 32.1% |
| basketball total | 3 | 33% | -37.0% ± 63.0% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
