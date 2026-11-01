# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 9497 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 1873 | 120 | 6% |
| football | 7624 | 2743 | 36% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 120 | 119 | 1% |
| basketball lines | 90 | 0 | 100% |
| basketball total | 120 | 118 | 2% |
| basketball win | 120 | 117 | 2% |
| football 1up | 2423 | 0 | 100% |
| football 1x2 | 2741 | 2691 | 2% |
| football 2up | 2423 | 0 | 100% |
| football btts | 2667 | 2464 | 8% |
| football dc | 2733 | 2546 | 7% |
| football ladder | 1717 | 0 | 100% |
| football ou1.5 | 2580 | 2461 | 5% |
| football ou2.5 | 2718 | 2665 | 2% |
| football ou3.5 | 2647 | 2557 | 3% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 6942 | 21% | -8.0% ± 1.8% | -4.6% ± 1.9% |
| football dc | 6594 | 5% | -7.8% ± 0.9% | -2.4% ± 1.0% |
| football o/u2.5 | 4584 | 9% | -6.2% ± 1.5% | -3.0% ± 1.5% |
| football o/u3.5 | 4428 | 12% | -7.1% ± 1.6% | -3.4% ± 1.7% |
| football o/u1.5 | 4300 | 8% | -9.6% ± 1.9% | -4.7% ± 2.1% |
| football btts | 4284 | 9% | -7.8% ± 1.5% | -4.1% ± 1.5% |
| basketball hcp | 214 | 37% | -3.9% ± 6.6% | -3.8% ± 6.6% |
| basketball win | 212 | 35% | +0.0% ± 9.2% | -0.6% ± 8.6% |
| basketball total | 212 | 36% | -4.4% ± 6.6% | -4.2% ± 6.6% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 292 | 35% | +4.3% ± 9.8% |
| football o/u3.5 | 46 | 46% | -21.9% ± 13.4% |
| football o/u2.5 | 38 | 47% | +5.4% ± 19.4% |
| football o/u1.5 | 33 | 27% | -14.9% ± 26.5% |
| football dc | 28 | 79% | +17.1% ± 13.2% |
| basketball win | 24 | 50% | +56.9% ± 53.8% |
| football btts | 22 | 41% | -12.4% ± 23.6% |
| basketball hcp | 13 | 54% | +5.5% ± 28.2% |
| basketball total | 8 | 38% | -28.5% ± 34.9% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
