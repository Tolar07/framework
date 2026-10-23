# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 2588 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 444 | 34 | 8% |
| football | 2144 | 899 | 42% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 34 | 33 | 3% |
| basketball lines | 10 | 0 | 100% |
| basketball total | 34 | 33 | 3% |
| basketball win | 34 | 33 | 3% |
| football 1up | 792 | 0 | 100% |
| football 1x2 | 898 | 879 | 2% |
| football 2up | 792 | 0 | 100% |
| football btts | 881 | 820 | 7% |
| football dc | 896 | 840 | 6% |
| football ladder | 68 | 0 | 100% |
| football ou1.5 | 863 | 825 | 4% |
| football ou2.5 | 890 | 878 | 1% |
| football ou3.5 | 875 | 844 | 4% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 2592 | 21% | -8.5% ± 2.9% | -5.2% ± 3.1% |
| football dc | 2475 | 4% | -7.8% ± 1.4% | -2.4% ± 1.6% |
| football o/u2.5 | 1724 | 9% | -5.8% ± 2.4% | -2.5% ± 2.5% |
| football o/u3.5 | 1654 | 13% | -6.9% ± 2.6% | -2.9% ± 2.8% |
| football o/u1.5 | 1622 | 7% | -5.4% ± 3.3% | +0.3% ± 3.6% |
| football btts | 1608 | 8% | -6.8% ± 2.4% | -2.9% ± 2.5% |
| basketball win | 66 | 44% | +7.1% ± 21.1% | +3.0% ± 18.5% |
| basketball total | 66 | 41% | -4.3% ± 11.9% | -5.3% ± 11.8% |
| basketball hcp | 66 | 48% | -3.7% ± 12.0% | -5.7% ± 11.7% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 126 | 29% | -14.1% ± 13.5% |
| football o/u2.5 | 17 | 53% | +26.9% ± 31.2% |
| football o/u3.5 | 17 | 53% | -2.0% ± 25.2% |
| football o/u1.5 | 12 | 42% | +17.0% ± 48.8% |
| football dc | 11 | 82% | +34.0% ± 22.7% |
| football btts | 10 | 50% | +15.6% ± 39.8% |
| basketball win | 9 | 44% | +131.4% ± 132.6% |
| basketball hcp | 5 | 80% | +60.0% ± 40.0% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
