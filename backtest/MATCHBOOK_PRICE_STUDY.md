# MATCHBOOK PRICE STUDY

Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet game the sweep watches, with Matchbook's best back price for the same market (`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its 2% commission. A study, not a selector.

Games kicking off from 2026-10-16: 7090 graded.

## 1. Coverage — what Matchbook lists

| Sport | Graded games | On Matchbook | Share |
|---|---:|---:|---:|
| basketball | 1346 | 97 | 7% |
| football | 5744 | 2098 | 37% |

SportyBet markets on games Matchbook lists — how often Matchbook has the same market (1UP/2UP early payout is SportyBet-only):

| Market | SportyBet | Matchbook too | Missing on Matchbook |
|---|---:|---:|---:|
| basketball hcp | 97 | 96 | 1% |
| basketball lines | 67 | 0 | 100% |
| basketball total | 97 | 95 | 2% |
| basketball win | 97 | 94 | 3% |
| football 1up | 1861 | 0 | 100% |
| football 1x2 | 2097 | 2052 | 2% |
| football 2up | 1861 | 0 | 100% |
| football btts | 2044 | 1898 | 7% |
| football dc | 2091 | 1943 | 7% |
| football ladder | 1072 | 0 | 100% |
| football ou1.5 | 1978 | 1889 | 4% |
| football ou2.5 | 2077 | 2038 | 2% |
| football ou3.5 | 2031 | 1966 | 3% |

## 2. Same market, both books

Every side priced at both. "SportyBet pays more" = SportyBet's price above Matchbook's after commission. Return = £1 on every side at that book.

| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |
|---|---:|---:|---:|---:|
| football 1x2 | 5451 | 21% | -7.8% ± 2.1% | -4.3% ± 2.2% |
| football dc | 5169 | 5% | -7.8% ± 1.0% | -2.4% ± 1.1% |
| football o/u2.5 | 3608 | 9% | -6.5% ± 1.6% | -3.3% ± 1.7% |
| football o/u3.5 | 3500 | 13% | -7.2% ± 1.8% | -3.5% ± 1.9% |
| football o/u1.5 | 3386 | 8% | -9.5% ± 2.1% | -4.4% ± 2.4% |
| football btts | 3382 | 9% | -7.9% ± 1.6% | -4.2% ± 1.7% |
| basketball hcp | 176 | 39% | -4.2% ± 7.2% | -4.2% ± 7.3% |
| basketball win | 174 | 36% | +0.9% ± 10.5% | -0.1% ± 9.8% |
| basketball total | 174 | 35% | -4.4% ± 7.3% | -4.5% ± 7.3% |

## 3. Mismatches — SportyBet above Matchbook's fair price

Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If Matchbook is the sharper book, backing these at SportyBet should return more than backing everything (section 2).

| Market | Mismatches | Won | Return at SportyBet |
|---|---:|---:|---:|
| football 1x2 | 241 | 34% | +0.6% ± 10.7% |
| football o/u3.5 | 37 | 49% | -14.2% ± 15.6% |
| football o/u2.5 | 32 | 44% | -0.0% ± 21.5% |
| football o/u1.5 | 28 | 25% | -27.7% ± 26.4% |
| basketball win | 22 | 45% | +50.7% ± 58.5% |
| football dc | 21 | 81% | +26.1% ± 15.5% |
| football btts | 16 | 38% | -15.9% ± 28.8% |
| basketball hcp | 12 | 50% | -1.8% ± 29.7% |
| basketball total | 6 | 33% | -36.7% ± 40.1% |

Small samples first: a return needs a few hundred sides before it means anything; ± is one standard error.
