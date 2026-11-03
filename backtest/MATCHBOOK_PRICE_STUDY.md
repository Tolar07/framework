# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 10362 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 2076 | 215 | 10% |
| football | 8286 | 3020 | 36% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 215 | 204 | 5% |
| basketball lines | 185 | 0 | 100% |
| basketball total | 215 | 210 | 2% |
| basketball win | 215 | 197 | 8% |
| football 1up | 2672 | 0 | 100% |
| football 1x2 | 3018 | 2963 | 2% |
| football 2up | 2672 | 0 | 100% |
| football btts | 2942 | 2721 | 8% |
| football dc | 3009 | 2807 | 7% |
| football ladder | 1994 | 0 | 100% |
| football ou1.5 | 2852 | 2720 | 5% |
| football ou2.5 | 2994 | 2938 | 2% |
| football ou3.5 | 2920 | 2814 | 4% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 7749 | 21% | -8.7% ± 1.7% | -5.4% ± 1.8% |
| football dc | 7368 | 5% | -8.1% ± 0.8% | -2.8% ± 0.9% |
| football o/u2.5 | 5124 | 9% | -6.4% ± 1.4% | -3.2% ± 1.4% |
| football o/u3.5 | 4936 | 12% | -7.4% ± 1.5% | -3.7% ± 1.6% |
| football o/u1.5 | 4812 | 8% | -9.9% ± 1.8% | -5.0% ± 2.0% |
| football btts | 4794 | 10% | -7.8% ± 1.4% | -4.1% ± 1.4% |
| basketball total | 396 | 32% | -5.5% ± 4.8% | -5.1% ± 4.8% |
| basketball hcp | 384 | 32% | -5.2% ± 4.9% | -4.5% ± 4.9% |
| basketball win | 372 | 25% | -5.5% ± 7.2% | +5.8% ± 14.5% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 322 | 34% | +2.6% ± 9.5% |
| football o/u3.5 | 54 | 46% | -18.3% ± 13.0% |
| football o/u2.5 | 40 | 48% | +5.0% ± 18.7% |
| football o/u1.5 | 37 | 30% | -1.4% ± 27.1% |
| football dc | 28 | 79% | +17.1% ± 13.2% |
| basketball win | 27 | 48% | +45.7% ± 48.4% |
| football btts | 24 | 46% | +1.5% ± 23.7% |
| basketball hcp | 18 | 56% | +7.6% ± 23.4% |
| basketball total | 11 | 36% | -31.1% ± 28.8% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
