# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 3103 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 579 | 45 | 8% |
| football | 2524 | 1036 | 41% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 45 | 44 | 2% |
| basketball lines | 20 | 0 | 100% |
| basketball total | 45 | 43 | 4% |
| basketball win | 45 | 44 | 2% |
| football 1up | 913 | 0 | 100% |
| football 1x2 | 1035 | 1015 | 2% |
| football 2up | 913 | 0 | 100% |
| football btts | 1018 | 943 | 7% |
| football dc | 1032 | 969 | 6% |
| football ladder | 186 | 0 | 100% |
| football ou1.5 | 991 | 947 | 4% |
| football ou2.5 | 1026 | 1011 | 1% |
| football ou3.5 | 1007 | 971 | 4% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 2943 | 20% | -9.0% ± 2.7% | -5.7% ± 2.9% |
| football dc | 2805 | 4% | -8.1% ± 1.3% | -2.6% ± 1.5% |
| football o/u2.5 | 1952 | 9% | -6.2% ± 2.2% | -2.9% ± 2.3% |
| football o/u3.5 | 1872 | 12% | -7.1% ± 2.4% | -3.1% ± 2.6% |
| football o/u1.5 | 1832 | 7% | -6.9% ± 3.0% | -1.5% ± 3.3% |
| football btts | 1822 | 9% | -7.4% ± 2.2% | -3.5% ± 2.3% |
| basketball win | 86 | 36% | +3.3% ± 17.0% | +0.6% ± 15.1% |
| basketball hcp | 86 | 41% | -4.2% ± 10.4% | -5.3% ± 10.3% |
| basketball total | 84 | 35% | -4.3% ± 10.5% | -4.5% ± 10.5% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 139 | 29% | -6.1% ± 14.9% |
| football o/u3.5 | 19 | 47% | -12.3% ± 23.6% |
| football o/u2.5 | 18 | 56% | +29.7% ± 29.5% |
| football o/u1.5 | 13 | 38% | +8.0% ± 45.8% |
| football dc | 11 | 82% | +34.0% ± 22.7% |
| football btts | 10 | 50% | +15.6% ± 39.8% |
| basketball win | 10 | 50% | +124.4% ± 118.8% |
| basketball hcp | 6 | 83% | +63.3% ± 32.8% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
