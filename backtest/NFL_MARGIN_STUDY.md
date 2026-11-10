# NFL margin-distribution walk-forward study

Made 2026-11-10 00:11 UTC by `backtest/nfl_margin_study.py` (framework#384, refs #339). 7411 NFL games with a closing spread (nflverse). Settings tried: **3** (shrink weight W); chosen on 2006-2015, reported on **2016-2026 only**.

Log loss of 'home wins by more than k' over every half-point line -20.5..20.5 (lower is better):

| Model (held-out 2016-2026, 2896 games) | All lines | Key-number lines (+-2.5/3.5/6.5/7.5) |
|---|---|---|
| A Normal, sd 13.45 fixed | 0.4533 | 0.5658 |
| B Normal, running sd | 0.4531 | 0.5655 |
| C empirical by spread, W=40 | 0.4517 | 0.5633 |

Share of games decided by exactly N points, held-out (2896 games), real vs Normal shape:

- 3 pts: real 14.7% vs Normal 5.5%
- 7 pts: real 8.5% vs Normal 5.0%
- 10 pts: real 4.7% vs Normal 4.4%

## Reading

- The empirical shape beats the Normal on the key-number lines by 0.0023 log loss held-out (+0.0014 over all lines): price NFL handicaps and bands near 3 and 7 from it, not a Normal. A shadow candidate only; it needs the shadow record before any bar uses it.
- 3 settings tried; the held-out line is the honest one.
- Means are the closing spread, i.e. the market's own number; this grades the SHAPE around it, not a better mean. No free alternate-line prices, so no return figure (PENDING, HR35).
- Record only: nothing here changes a stake, a bar or the live switch.
