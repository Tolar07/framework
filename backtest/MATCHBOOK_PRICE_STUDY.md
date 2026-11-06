# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 10915 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 2283 | 307 | 13% |
| football | 8632 | 3189 | 37% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 307 | 295 | 4% |
| basketball lines | 277 | 0 | 100% |
| basketball total | 307 | 300 | 2% |
| basketball win | 307 | 279 | 9% |
| football 1up | 2825 | 0 | 100% |
| football 1x2 | 3187 | 3132 | 2% |
| football 2up | 2825 | 0 | 100% |
| football btts | 3108 | 2887 | 7% |
| football dc | 3178 | 2976 | 6% |
| football ladder | 2163 | 0 | 100% |
| football ou1.5 | 3015 | 2883 | 4% |
| football ou2.5 | 3161 | 3105 | 2% |
| football ou3.5 | 3086 | 2980 | 3% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 8256 | 21% | -8.7% ± 1.7% | -5.3% ± 1.8% |
| football dc | 7875 | 5% | -8.1% ± 0.8% | -2.8% ± 0.9% |
| football o/u2.5 | 5458 | 9% | -6.3% ± 1.3% | -3.1% ± 1.4% |
| football o/u3.5 | 5268 | 12% | -7.7% ± 1.4% | -4.1% ± 1.5% |
| football o/u1.5 | 5138 | 8% | -9.4% ± 1.7% | -4.4% ± 1.9% |
| football btts | 5126 | 10% | -7.7% ± 1.3% | -3.9% ± 1.4% |
| basketball total | 576 | 31% | -5.7% ± 3.9% | -5.0% ± 4.0% |
| basketball hcp | 566 | 30% | -5.5% ± 4.0% | -4.5% ± 4.0% |
| basketball win | 536 | 25% | -7.0% ± 5.7% | +1.4% ± 10.5% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 348 | 35% | +4.1% ± 9.2% |
| football o/u3.5 | 58 | 47% | -17.9% ± 12.5% |
| football o/u2.5 | 40 | 48% | +5.0% ± 18.7% |
| football o/u1.5 | 37 | 30% | -1.4% ± 27.1% |
| basketball win | 36 | 44% | +41.1% ± 39.9% |
| football dc | 30 | 77% | +13.4% ± 12.9% |
| football btts | 26 | 50% | +10.8% ± 22.8% |
| basketball hcp | 20 | 50% | -3.2% ± 22.2% |
| basketball total | 15 | 33% | -36.7% ± 23.9% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
