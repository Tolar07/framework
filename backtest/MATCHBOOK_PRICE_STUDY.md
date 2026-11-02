# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 10083 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 1947 | 121 | 6% |
| football | 8136 | 2938 | 36% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 121 | 120 | 1% |
| basketball lines | 91 | 0 | 100% |
| basketball total | 121 | 119 | 2% |
| basketball win | 121 | 118 | 2% |
| football 1up | 2601 | 0 | 100% |
| football 1x2 | 2936 | 2884 | 2% |
| football 2up | 2601 | 0 | 100% |
| football btts | 2861 | 2642 | 8% |
| football dc | 2927 | 2729 | 7% |
| football ladder | 1912 | 0 | 100% |
| football ou1.5 | 2770 | 2640 | 5% |
| football ou2.5 | 2912 | 2857 | 2% |
| football ou3.5 | 2838 | 2735 | 4% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 7515 | 21% | -8.3% ± 1.7% | -5.0% ± 1.8% |
| football dc | 7137 | 5% | -7.9% ± 0.8% | -2.6% ± 0.9% |
| football o/u2.5 | 4964 | 9% | -6.3% ± 1.4% | -3.2% ± 1.5% |
| football o/u3.5 | 4780 | 12% | -7.3% ± 1.5% | -3.7% ± 1.6% |
| football o/u1.5 | 4654 | 8% | -9.9% ± 1.8% | -5.0% ± 2.0% |
| football btts | 4638 | 10% | -7.8% ± 1.4% | -4.1% ± 1.5% |
| basketball hcp | 216 | 38% | -3.9% ± 6.6% | -3.8% ± 6.6% |
| basketball win | 214 | 35% | -0.1% ± 9.1% | -0.8% ± 8.6% |
| basketball total | 214 | 36% | -4.3% ± 6.6% | -4.2% ± 6.6% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 316 | 35% | +4.5% ± 9.6% |
| football o/u3.5 | 52 | 46% | -21.7% ± 12.5% |
| football o/u2.5 | 38 | 47% | +5.4% ± 19.4% |
| football o/u1.5 | 37 | 30% | -1.4% ± 27.1% |
| football dc | 28 | 79% | +17.1% ± 13.2% |
| basketball win | 25 | 52% | +57.4% ± 51.6% |
| football btts | 24 | 46% | +1.5% ± 23.7% |
| basketball hcp | 14 | 57% | +11.4% ± 26.8% |
| basketball total | 8 | 38% | -28.5% ± 34.9% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
