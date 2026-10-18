# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 1072 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 152 | 4 | 3% |
| football | 920 | 360 | 39% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 4 | 3 | 25% |
| basketball total | 4 | 4 | 0% |
| basketball win | 4 | 4 | 0% |
| football 1up | 321 | 0 | 100% |
| football 1x2 | 360 | 350 | 3% |
| football 2up | 321 | 0 | 100% |
| football btts | 354 | 307 | 13% |
| football dc | 359 | 320 | 11% |
| football ou1.5 | 349 | 321 | 8% |
| football ou2.5 | 358 | 349 | 3% |
| football ou3.5 | 354 | 327 | 8% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 1050 | 21% | -8.0% ± 4.6% | -5.0% ± 4.8% |
| football dc | 960 | 4% | -7.8% ± 2.3% | -2.4% ± 2.6% |
| football o/u2.5 | 698 | 10% | -4.9% ± 3.8% | -1.9% ± 3.9% |
| football o/u3.5 | 654 | 13% | -7.1% ± 4.1% | -3.8% ± 4.4% |
| football o/u1.5 | 642 | 10% | -4.4% ± 5.2% | +0.5% ± 5.7% |
| football btts | 614 | 11% | -6.7% ± 3.9% | -2.9% ± 4.1% |
| basketball win | 8 | 12% | +7.7% ± 46.7% | +13.7% ± 49.5% |
| basketball total | 8 | 0% | -6.7% ± 35.3% | -4.8% ± 36.0% |
| basketball hcp | 6 | 0% | -6.8% ± 41.7% | -3.1% ± 43.3% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 52 | 27% | -17.9% ± 21.1% |
| football o/u3.5 | 10 | 70% | +32.5% ± 33.7% |
| football o/u2.5 | 8 | 50% | +7.3% ± 41.8% |
| football dc | 8 | 75% | +12.5% ± 26.1% |
| football o/u1.5 | 6 | 50% | +39.0% ± 71.4% |
| football btts | 3 | 0% | -100.0% ± 0.0% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
