# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 4739 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 877 | 56 | 6% |
| football | 3862 | 1442 | 37% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 56 | 55 | 2% |
| basketball lines | 30 | 0 | 100% |
| basketball total | 56 | 54 | 4% |
| basketball win | 56 | 55 | 2% |
| football 1up | 1277 | 0 | 100% |
| football 1x2 | 1441 | 1406 | 2% |
| football 2up | 1277 | 0 | 100% |
| football btts | 1417 | 1299 | 8% |
| football dc | 1438 | 1329 | 8% |
| football ladder | 533 | 0 | 100% |
| football ou1.5 | 1372 | 1305 | 5% |
| football ou2.5 | 1429 | 1402 | 2% |
| football ou3.5 | 1405 | 1347 | 4% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 3945 | 21% | -8.0% ± 2.4% | -4.6% ± 2.5% |
| football dc | 3735 | 4% | -7.8% ± 1.2% | -2.3% ± 1.3% |
| football o/u2.5 | 2618 | 9% | -6.4% ± 1.9% | -3.2% ± 2.0% |
| football o/u3.5 | 2520 | 13% | -7.5% ± 2.1% | -3.7% ± 2.2% |
| football o/u1.5 | 2450 | 8% | -7.9% ± 2.6% | -2.6% ± 2.9% |
| football btts | 2438 | 9% | -7.9% ± 1.9% | -4.1% ± 2.0% |
| basketball win | 106 | 31% | +0.3% ± 14.4% | -1.6% ± 12.9% |
| basketball hcp | 106 | 37% | -4.4% ± 9.3% | -4.9% ± 9.3% |
| basketball total | 104 | 30% | -4.3% ± 9.4% | -4.4% ± 9.4% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 174 | 30% | -9.9% ± 12.6% |
| football o/u3.5 | 28 | 43% | -25.0% ± 17.9% |
| football o/u2.5 | 27 | 41% | -7.1% ± 22.9% |
| football o/u1.5 | 24 | 25% | -28.2% ± 28.8% |
| football dc | 14 | 79% | +26.1% ± 20.3% |
| football btts | 12 | 42% | -3.7% ± 35.4% |
| basketball win | 11 | 45% | +104.0% ± 109.4% |
| basketball hcp | 6 | 83% | +63.3% ± 32.8% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
