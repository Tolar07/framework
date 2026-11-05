# Ice hockey backtest (NHL, walk-forward)

Written by `backtest/hockey_backtest.py` on 2026-11-05 21:49 UTC. Standing order 50.

* Games: 4186 NHL regular-season games, seasons 20232024, 20242025, 20252026, 20262027.
* Refit every 7 days on games before a 1-day purge gap; never on the game scored.
* Settings tried: 9 (half-life [90.0, 180.0, 365.0] x draw boost [1.0, 1.15, 1.3]), chosen on 20242025 only: **half-life 365 days, draw boost x1.3**.
* Reported on later games only (20252026, 20262027, 1562 games; the current season is partial).
* No free historical closing odds for hockey: this is accuracy, not return. Return and value
  against the exchange close come from the shadow board's graded record (`data/ice_hockey/scoreboard.json`).

| Market | n | Brier: league rate | Brier: plain model | Brier: chosen model | Log loss (chosen) |
|---|---|---|---|---|---|
| 1|Home | 1562 | 0.2419 | 0.2385 | 0.2378 | 0.6683 |
| 1|Draw | 1562 | 0.1858 | 0.1909 | 0.1862 | 0.5610 |
| 1|Away | 1562 | 0.2283 | 0.2257 | 0.2258 | 0.6434 |
| 406|Home | 1562 | 0.2497 | 0.2471 | 0.2480 | 0.6893 |
| 18|Over 5.5 | 1562 | 0.2447 | 0.2455 | 0.2449 | 0.6829 |
| 410|Home (+1.5) | 1562 | 0.1960 | 0.1937 | 0.1954 | 0.5810 |

Overall Brier: league rate 0.22441, plain model 0.22356, chosen 0.22303.

All tries on the tuning season:

* half-life 365, draw x1.3: 0.21794
* half-life 180, draw x1.3: 0.21799
* half-life 365, draw x1.15: 0.21809
* half-life 180, draw x1.15: 0.21812
* half-life 365, draw x1.0: 0.21844
* half-life 180, draw x1.0: 0.21847
* half-life 90, draw x1.3: 0.21906
* half-life 90, draw x1.15: 0.21921
* half-life 90, draw x1.0: 0.21959
