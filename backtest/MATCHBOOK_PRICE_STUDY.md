# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 109 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 29 | 0 | 0% |
| football | 80 | 21 | 26% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| football 1up | 20 | 0 | 100% |
| football 1x2 | 21 | 21 | 0% |
| football 2up | 20 | 0 | 100% |
| football btts | 21 | 21 | 0% |
| football dc | 21 | 21 | 0% |
| football ou1.5 | 21 | 21 | 0% |
| football ou2.5 | 21 | 21 | 0% |
| football ou3.5 | 21 | 21 | 0% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 63 | 22% | -9.6% ± 17.6% | -7.1% ± 18.3% |
| football dc | 63 | 3% | -7.9% ± 8.7% | -3.2% ± 9.4% |
| football o/u1.5 | 42 | 5% | -2.0% ± 20.2% | +3.3% ± 21.8% |
| football o/u2.5 | 42 | 5% | -6.0% ± 15.0% | -2.8% ± 15.6% |
| football o/u3.5 | 42 | 10% | +5.2% ± 19.1% | +10.0% ± 20.4% |
| football btts | 42 | 14% | -11.4% ± 14.1% | -7.7% ± 14.7% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 1 | 100% | +53.0% ± 0.0% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
