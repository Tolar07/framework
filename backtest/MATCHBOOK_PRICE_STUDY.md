# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 7891 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 1561 | 113 | 7% |
| football | 6330 | 2339 | 37% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 113 | 112 | 1% |
| basketball lines | 83 | 0 | 100% |
| basketball total | 113 | 111 | 2% |
| basketball win | 113 | 110 | 3% |
| football 1up | 2061 | 0 | 100% |
| football 1x2 | 2337 | 2291 | 2% |
| football 2up | 2061 | 0 | 100% |
| football btts | 2272 | 2111 | 7% |
| football dc | 2329 | 2170 | 7% |
| football ladder | 1313 | 0 | 100% |
| football ou1.5 | 2197 | 2098 | 5% |
| football ou2.5 | 2315 | 2270 | 2% |
| football ou3.5 | 2255 | 2189 | 3% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 5949 | 21% | -8.1% ± 2.0% | -4.6% ± 2.1% |
| football dc | 5646 | 5% | -7.9% ± 0.9% | -2.4% ± 1.0% |
| football o/u2.5 | 3932 | 9% | -6.4% ± 1.6% | -3.2% ± 1.6% |
| football o/u3.5 | 3820 | 13% | -7.3% ± 1.7% | -3.7% ± 1.8% |
| football o/u1.5 | 3688 | 8% | -9.3% ± 2.1% | -4.2% ± 2.3% |
| football btts | 3688 | 10% | -7.9% ± 1.6% | -4.2% ± 1.6% |
| basketball hcp | 202 | 38% | -4.0% ± 6.8% | -3.9% ± 6.8% |
| basketball win | 200 | 36% | +1.9% ± 9.7% | +1.2% ± 9.1% |
| basketball total | 200 | 36% | -4.4% ± 6.8% | -4.4% ± 6.8% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 258 | 34% | +1.0% ± 10.4% |
| football o/u3.5 | 41 | 44% | -22.6% ± 14.6% |
| football o/u2.5 | 34 | 44% | +1.9% ± 21.1% |
| football o/u1.5 | 29 | 24% | -30.2% ± 25.6% |
| football dc | 23 | 74% | +15.2% ± 16.0% |
| basketball win | 23 | 48% | +56.2% ± 56.2% |
| football btts | 22 | 41% | -12.4% ± 23.6% |
| basketball hcp | 12 | 50% | -1.8% ± 29.7% |
| basketball total | 7 | 43% | -18.3% ± 38.5% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
