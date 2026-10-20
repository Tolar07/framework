# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 2032 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 270 | 4 | 1% |
| football | 1762 | 693 | 39% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 4 | 3 | 25% |
| basketball total | 4 | 4 | 0% |
| basketball win | 4 | 4 | 0% |
| football 1up | 608 | 0 | 100% |
| football 1x2 | 692 | 675 | 2% |
| football 2up | 608 | 0 | 100% |
| football btts | 678 | 620 | 9% |
| football dc | 690 | 637 | 8% |
| football ou1.5 | 665 | 629 | 5% |
| football ou2.5 | 684 | 672 | 2% |
| football ou3.5 | 678 | 647 | 5% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 2004 | 21% | -8.9% ± 3.3% | -5.6% ± 3.5% |
| football dc | 1890 | 4% | -8.0% ± 1.6% | -2.7% ± 1.8% |
| football o/u2.5 | 1328 | 10% | -5.4% ± 2.7% | -2.1% ± 2.8% |
| football o/u3.5 | 1276 | 13% | -7.4% ± 3.0% | -3.6% ± 3.2% |
| football o/u1.5 | 1242 | 9% | -3.9% ± 3.8% | +2.0% ± 4.2% |
| football btts | 1224 | 10% | -6.7% ± 2.8% | -2.9% ± 2.9% |
| basketball win | 8 | 12% | +7.7% ± 46.7% | +13.7% ± 49.5% |
| basketball total | 8 | 0% | -6.7% ± 35.3% | -4.8% ± 36.0% |
| basketball hcp | 6 | 0% | -6.8% ± 41.7% | -3.1% ± 43.3% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 95 | 24% | -28.6% ± 14.4% |
| football o/u3.5 | 15 | 53% | -1.5% ± 27.2% |
| football o/u2.5 | 14 | 43% | -0.5% ± 33.1% |
| football o/u1.5 | 12 | 42% | +17.0% ± 48.8% |
| football btts | 10 | 50% | +15.6% ± 39.8% |
| football dc | 10 | 80% | +27.4% ± 24.0% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
