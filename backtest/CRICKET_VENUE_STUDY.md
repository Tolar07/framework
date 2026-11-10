# Cricket venue + format first-innings total study

Made 2026-11-10 00:26 UTC by `backtest/cricket_venue_study.py` (framework#385, record-only). 5842 full first innings (T20 3433, ODI 2409), men's, Cricsheet. Settings tried: **8** (venue shrinkage k x format-mean decay); chosen on 2010-2018, reported on **2019-2026 only**.

| Rule (held-out years) | Matches | MAE runs |
|---|---|---|
| FORMAT mean only (no venue) | 3677 | 40.1 |
| VENUE shrunk: k=20, decay=0.02 | 3677 | 39.3 |
|   T20: format only | 2853 | 35.3 |
|   T20: venue shrunk | 2853 | 34.4 |
|   ODI: format only | 824 | 56.6 |
|   ODI: venue shrunk | 824 | 56.1 |

## Reading

- Venue knowledge changes the first-innings guess by +0.79 runs of average error (40.1 -> 39.3); it helps, so a venue baseline belongs beside the totals line as a shadow.
- 8 settings tried; the held-out line is the honest one.
- Pitch type (green / dusty / flat), toss and line-ups are not in Cricsheet: PENDING, venue is the proxy.
- No free historical closing totals, so no return figure: CLV comes from the shadow record.
- Record only: nothing here changes a stake, a bar or the live switch.
