# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 1863 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 237 | 4 | 2% |
| football | 1626 | 622 | 38% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 4 | 3 | 25% |
| basketball total | 4 | 4 | 0% |
| basketball win | 4 | 4 | 0% |
| football 1up | 542 | 0 | 100% |
| football 1x2 | 621 | 604 | 3% |
| football 2up | 542 | 0 | 100% |
| football btts | 607 | 550 | 9% |
| football dc | 619 | 566 | 9% |
| football ou1.5 | 596 | 561 | 6% |
| football ou2.5 | 613 | 601 | 2% |
| football ou3.5 | 607 | 576 | 5% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 1794 | 21% | -8.7% ± 3.5% | -5.4% ± 3.7% |
| football dc | 1680 | 5% | -7.9% ± 1.7% | -2.5% ± 1.9% |
| football o/u2.5 | 1188 | 10% | -5.7% ± 2.9% | -2.5% ± 3.0% |
| football o/u3.5 | 1136 | 14% | -7.2% ± 3.1% | -3.6% ± 3.3% |
| football o/u1.5 | 1108 | 10% | -4.2% ± 4.0% | +1.3% ± 4.4% |
| football btts | 1086 | 10% | -6.8% ± 2.9% | -3.1% ± 3.0% |
| basketball win | 8 | 12% | +7.7% ± 46.7% | +13.7% ± 49.5% |
| basketball total | 8 | 0% | -6.7% ± 35.3% | -4.8% ± 36.0% |
| basketball hcp | 6 | 0% | -6.8% ± 41.7% | -3.1% ± 43.3% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 88 | 25% | -25.2% ± 15.3% |
| football o/u3.5 | 15 | 53% | -1.5% ± 27.2% |
| football o/u2.5 | 13 | 46% | +7.2% ± 34.8% |
| football o/u1.5 | 12 | 42% | +17.0% ± 48.8% |
| football dc | 10 | 80% | +27.4% ± 24.0% |
| football btts | 9 | 44% | +2.9% ± 42.2% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
