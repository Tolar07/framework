# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 10570 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 2137 | 239 | 11% |
| football | 8433 | 3094 | 37% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 239 | 227 | 5% |
| basketball lines | 209 | 0 | 100% |
| basketball total | 239 | 232 | 3% |
| basketball win | 239 | 216 | 10% |
| football 1up | 2744 | 0 | 100% |
| football 1x2 | 3092 | 3037 | 2% |
| football 2up | 2744 | 0 | 100% |
| football btts | 3016 | 2795 | 7% |
| football dc | 3083 | 2881 | 7% |
| football ladder | 2068 | 0 | 100% |
| football ou1.5 | 2923 | 2791 | 5% |
| football ou2.5 | 3068 | 3012 | 2% |
| football ou3.5 | 2992 | 2886 | 4% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 7971 | 21% | -8.8% ± 1.7% | -5.5% ± 1.8% |
| football dc | 7590 | 5% | -8.1% ± 0.8% | -2.8% ± 0.9% |
| football o/u2.5 | 5272 | 9% | -6.3% ± 1.4% | -3.1% ± 1.4% |
| football o/u3.5 | 5080 | 12% | -7.6% ± 1.5% | -3.9% ± 1.6% |
| football o/u1.5 | 4954 | 8% | -9.3% ± 1.8% | -4.3% ± 2.0% |
| football btts | 4942 | 10% | -7.7% ± 1.4% | -3.9% ± 1.4% |
| basketball total | 440 | 31% | -5.6% ± 4.5% | -5.1% ± 4.5% |
| basketball hcp | 430 | 32% | -5.4% ± 4.6% | -4.7% ± 4.6% |
| basketball win | 410 | 25% | -6.6% ± 6.8% | +4.1% ± 13.4% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 333 | 34% | +3.3% ± 9.3% |
| football o/u3.5 | 55 | 45% | -19.8% ± 12.9% |
| football o/u2.5 | 40 | 48% | +5.0% ± 18.7% |
| football o/u1.5 | 37 | 30% | -1.4% ± 27.1% |
| football dc | 30 | 77% | +13.4% ± 12.9% |
| basketball win | 30 | 43% | +31.2% ± 44.2% |
| football btts | 26 | 50% | +10.8% ± 22.8% |
| basketball hcp | 18 | 56% | +7.6% ± 23.4% |
| basketball total | 11 | 36% | -31.1% ± 28.8% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
