# Tennis format shadow

Made 2026-11-09 22:28 UTC by `backtest/tennis_format_study.py` (framework#380). Record only, walk-forward.

Data: 31271 completed ATP/WTA matches with a Pinnacle close (tennis-data.co.uk); 3277 are best-of-5.
Candidate (one try): best-of-5 price -> same players' best-of-3 chance (hold/break chain, tiebreak, serve 64% between equals, an assumption) -> slope learned on EARLIER years' best-of-3 matches -> back to best-of-5. Compared with the market on best-of-5 matches only.

| Year | Slope k (from earlier Bo3) | Bo5 matches | Brier market | Brier candidate | Bets (edge >= 2%) | Hit | ROI at the close |
|---|---|---|---|---|---|---|---|
| 2020 | 1.08 | 371 | 0.1602 | 0.1597 | 0 | - | - |
| 2021 | 1.07 | 487 | 0.1743 | 0.1746 | 0 | - | - |
| 2022 | 1.09 | 487 | 0.1633 | 0.1629 | 0 | - | - |
| 2023 | 1.08 | 495 | 0.1757 | 0.1760 | 0 | - | - |
| 2024 | 1.08 | 485 | 0.1548 | 0.1540 | 0 | - | - |
| 2025 | 1.08 | 465 | 0.1808 | 0.1810 | 0 | - | - |

All scored years: 2790 best-of-5 matches, Brier market 0.1685, candidate 0.1683 (candidate better by 0.0002). Held-out (last year) is the final row. A Brier gap this small on ~2790 matches is inside noise unless it repeats every year; nothing is promoted from this table alone.

## Reading

- Pinnacle's close is the sharp benchmark; beating it on Brier or at the close is rare, so a null result is the expected, honest outcome. The value of the module is the format conversion for markets that have no sharp price (volleyball, table tennis, darts, snooker legs / frames, exchange prices in short formats).
- Practitioner claims behind the idea: favourites win more often the longer the format (Pinnacle video @ 01:32 and Action Network video @ 04:09, as cited in framework#380; not re-watched here). Record only; no stake, bar or live switch reads this.
