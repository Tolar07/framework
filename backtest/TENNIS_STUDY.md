# Tennis walk-forward backtest

Made 2026-11-06 19:41 UTC by `backtest/tennis_backtest.py` (framework#345). 31271 completed matches with a Pinnacle close (ATP 16296, WTA 14975; tennis-data.co.uk). Tries counted: **22** (K x surface mix x market weight, then the edge bars on two models); chosen on 2019-2022, reported on **2023-2025 only**.

| Rule (held-out years) | Matches | Brier | Log loss | Winner hit rate | Pinnacle close log loss |
|---|---|---|---|---|---|
| Elo K32 alone (no market) | 13483 | 0.2192 | 0.6274 | 64.2% | 0.5956 |
| Best on tuning years: K48, surface 50%, market weight 50% | 13483 | 0.2101 | 0.6059 | 66.4% | 0.5956 |

Pinnacle's favourite won 68.0% of the same held-out matches.

## Flat-stake test (model vs Pinnacle close, priced at the market-average close)

| Setting | Edge bar | Bets | ROI per unit |
|---|---|---|---|
| Elo K32 alone | 3% | 9880 | -10.8% |
| Elo K32 alone | 5% | 7877 | -11.3% |
| Best on tuning years | 3% | 7148 | -10.4% |
| Best on tuning years | 5% | 4265 | -11.2% |

## Reading

- Elo alone log loss 0.6274 vs Pinnacle's close 0.5956: the closing price is the better chance; the Elo adds nothing on its own.
- Market-anchored best setting log loss 0.6059 vs Pinnacle 0.5956: no information beyond the price held-out: price the sport off the exchange.
- 22 tries made; the held-out lines are the honest ones, and any ROI above is one of them, not a result to bank.
- Bookmaker average prices carry a margin; exchange commission is not modelled. Rows without a price are skipped.
- Record only: nothing here changes a stake, a bar, a threshold or the live switch.
