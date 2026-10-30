# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 7343 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 1413 | 103 | 7% |
| football | 5930 | 2182 | 37% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 103 | 102 | 1% |
| basketball lines | 73 | 0 | 100% |
| basketball total | 103 | 101 | 2% |
| basketball win | 103 | 100 | 3% |
| football 1up | 1930 | 0 | 100% |
| football 1x2 | 2181 | 2136 | 2% |
| football 2up | 1930 | 0 | 100% |
| football btts | 2117 | 1970 | 7% |
| football dc | 2174 | 2023 | 7% |
| football ladder | 1156 | 0 | 100% |
| football ou1.5 | 2054 | 1964 | 4% |
| football ou2.5 | 2159 | 2120 | 2% |
| football ou3.5 | 2103 | 2038 | 3% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 5631 | 21% | -8.2% ± 2.0% | -4.8% ± 2.1% |
| football dc | 5340 | 5% | -8.0% ± 1.0% | -2.6% ± 1.1% |
| football o/u2.5 | 3726 | 9% | -6.4% ± 1.6% | -3.2% ± 1.7% |
| football o/u3.5 | 3612 | 13% | -7.3% ± 1.7% | -3.6% ± 1.9% |
| football o/u1.5 | 3502 | 8% | -9.3% ± 2.1% | -4.2% ± 2.3% |
| football btts | 3490 | 10% | -7.8% ± 1.6% | -4.1% ± 1.7% |
| basketball hcp | 186 | 38% | -4.1% ± 7.1% | -4.1% ± 7.1% |
| basketball win | 184 | 36% | +1.3% ± 10.2% | +0.5% ± 9.5% |
| basketball total | 184 | 35% | -4.4% ± 7.1% | -4.4% ± 7.1% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 254 | 33% | +0.2% ± 10.4% |
| football o/u3.5 | 40 | 45% | -20.6% ± 14.8% |
| football o/u2.5 | 33 | 42% | -3.1% ± 21.1% |
| football o/u1.5 | 29 | 24% | -30.2% ± 25.6% |
| football dc | 23 | 74% | +15.2% ± 16.0% |
| basketball win | 22 | 45% | +50.7% ± 58.5% |
| football btts | 20 | 35% | -23.5% ± 24.6% |
| basketball hcp | 12 | 50% | -1.8% ± 29.7% |
| basketball total | 7 | 43% | -18.3% ± 38.5% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
