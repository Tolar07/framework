# Darts format-length underdog study

Made 2026-11-07 10:55 UTC by `backtest/darts_format_underdog_study.py` (framework#341). Record only.

Data: 691 PDC World Championship matches, board K 24; only matches where both players already had 8+ games count. Idea: Action Network @ 04:09 (said only).

## Underdog win rate by match length (4 buckets, all shown)

| Winner needed (sets) | Matches | Underdog Elo chance | Underdog actual | Verdict |
|---|---|---|---|---|
| up to 3 | 25 | 0.4394 | 0.36 | PENDING (needs 30, has 25) |
| 4 | 45 | 0.4322 | 0.4 | underdogs win LESS than Elo says |
| 5 | 14 | 0.4383 | 0.5 | PENDING (needs 30, has 14) |
| 6+ | 10 | 0.4364 | 0.3 | PENDING (needs 30, has 10) |

Read it as: if short matches show underdogs winning MORE than Elo says and long ones LESS, a length term may be worth a shadow candidate next to the price. Only a lead: confirm on new matches before proposing anything.

Record only: nothing here changes a stake, a bar or the live switch.
