# LIVE REVIEW — 2026-10-14

First matchday followed by GitHub Actions instead of a Claude session
(`live.yml` run 1, `monitor/live_loop.py`). Provenance for every figure below:
**906 snapshots** in `data/study/2026-10-14/live/`, written by that run between
17:15:49 and 20:57:54 UTC and committed to `main` in 9 commits; the two 16:45
kickoffs also carry the session tracker's earlier rows (16:36–17:01). Final
scores and xG are FotMob's, as recorded in those snapshots. Settlement uses
`engine.picks_ledger._settle` and `engine.half.settle`, not arithmetic by hand.

## The board: 13 of 13

| KO | match | pick | px | HT | FT | 2H goals |
|---|---|---|---|---|---|---|
| 16:45 | Feyenoord v Como | DC | 1.26 | 1-1 | 3-2 | 3 |
| 16:45 | LASK v Liverpool | DC & Over 1.5 | 1.24 | 0-3 | 3-6 | 6 |
| 18:45 | Norwich v Southampton | Southampton +1.5 AH | 1.22 | 0-0 | 0-1 | 1 |
| 18:45 | Portsmouth v Sheffield Utd | Sheff Utd +1.5 AH | 1.23 | 1-0 | 3-2 | 4 |
| 18:45 | QPR v Derby | DC | 1.26 | 3-0 | 4-1 | 2 |
| 19:00 | Lincoln v West Ham | West Ham or draw | 1.20 | 0-1 | 0-6 | 5 |
| 19:00 | Villa v Fenerbahçe | DC | 1.24 | 3-0 | 6-0 | 3 |
| 19:00 | Betis v Porto | Betis Over 0.5 | 1.20 | 0-0 | 3-2 | 5 |
| 19:00 | Bodø/Glimt v Dortmund | DC | 1.26 | 0-0 | 1-0 | 1 |
| 19:00 | Man City v PSG | DC | 1.27 | 0-3 | 2-4 | 3 |
| 19:00 | Roma v Real Madrid | DC | 1.26 | 1-1 | 3-4 | 5 |
| 19:00 | Shakhtar v AEK | Over 1.5 | 1.26 | 1-1 | 3-1 | 2 |
| 19:00 | Slovan v Stuttgart | Stuttgart Over 1.5 | 1.28 | 0-1 | 0-3 | 2 |

**13 won, 0 lost. +3.18u on 13u staked (+24.5%).**

## The study board: 11 of 13

Same fixtures, one market each, none repeated (`engine_board.json`).
**11 won, 2 lost. +0.93u on 13u (+7.2%).** The two losses say more than the wins:

- **Lincoln v West Ham, Under 4.5 @1.20 — lost 0-6.** The profile read that
  order 43 exists to catch: West Ham's xG was 1.16 by half time against 0.09.
- **Bodø/Glimt v Dortmund, BTTS Yes @1.38 — lost 1-0.** The only match of the
  thirteen where one side failed to score.

## Why 13 of 13 happened, honestly

**42 second-half goals across 13 matches — 3.2 per game.** Twelve of the
thirteen produced at least one. The card was almost entirely double chance and
Over 1.5, and a night that goal-heavy pays both of those regardless of how the
picks were chosen. Four matches were level or one-goal at half time and
finished with five second-half goals between the sides.

So: a very good night, and **not evidence the price problem is solved.** Every
pick was 1.20–1.28 — the band `backtest/PRICE_BAND_STUDY.md` shows at −1.2%
(1.00–1.25, 207 picks) and −0.6% (1.25–1.30, 94). This is what that band looks
like when the night runs with you. The 332-single record stands at −3.4%.

## The question we could NOT answer — and why

The Architect asked (13 Oct) whether SportyBet's in-play prices lag what the xG
shows. **That cannot be answered from tonight's data.**

- 13 of 13 half-time snapshots carry the xG. **0 of 13 carry a SportyBet live
  price.** Of 906 rows, only **14** have one — all from the two 16:45 matches
  between 16:46 and 17:01, i.e. only while the SESSION tracker was running.
- Cause, from the run log, on every round after that:
  `SportyBet live feed failed (HTTP Error 403: Forbidden)`.
- **It is not a blanket block of Actions.** The same `daily.yml` run on Actions
  fetched 13/13 live prices and booked 13/13 codes from SportyBet today. The
  403 is specific to the in-play endpoint the tracker uses
  (`factsCenter/liveOrPrematchEvents`), while the board's
  `factsCenter/pcUpcomingEvents` works from a runner.

**This is a real cost of moving to Actions that I did not foresee**: the xG half
of the feature got better (free, durable, 906 rows, all 13 matches), and the
price half stopped working entirely. The question needs either an in-play
endpoint that answers a runner, or the price side captured somewhere else.
Until then this review reports xG only, and says so rather than implying the
comparison was made.

## What the xG alone did say

Four matches where the half-time score and the xG disagreed sharply:

| match | HT | xG at HT | FT |
|---|---|---|---|
| Lincoln v West Ham | 0-1 | 0.09 – 1.16 | 0-6 |
| Portsmouth v Sheffield Utd | 1-0 | 0.49 – 1.35 | 3-2 |
| Man City v PSG | 0-3 | 0.70 – 0.87 | 2-4 |
| Villa v Fenerbahçe | 3-0 | 0.70 – 1.33 | 6-0 |

Three of the four resolved towards the xG (West Ham ran away with it;
Sheffield United scored twice more; the City–PSG margin closed). **The fourth
went hard against it** — Fenerbahçe's higher half-time xG preceded a 6-0 loss.
On 13 matches this is an observation, not a finding, and it is the reason the
price comparison matters: xG alone is not enough to say the market was slow.

## Fixed tonight

- Every snapshot row now carries `home`, `away` and `kickoff_utc`. Five of the
  thirteen board picks had `fotmob_id = None` in the picks ledger, so their
  snapshots could not be joined back to the pick they were tracking even though
  the tracker had followed all thirteen by name. The files were keyed by FotMob
  id alone; they are not any more.

## Open

1. **The in-play price endpoint** (above). Without it the live tracker is an xG
   recorder, not the price-lag instrument it was built to be.
2. BTTS slips and accas for 14 Oct are not graded in this review — the board
   and study singles are. PENDING.
