# Multi-sport rollout: one new sport a week

Standing order 50 (Architect 2026-11-05). Schedule and switches: `config/sport_rollout.json`
(guarded by `tests/standing_orders_test.py`). One GitHub issue per sport, label `multi-sport`.

## The two weeks every sport gets

**Week A: build, backtest, shadow.**

1. Data feed: fixtures, results, line-ups/team news, and odds from all three venues
   (Matchbook, Betfair, SportyBet), mapped to one event id.
2. Model: the method the sport's own evidence supports (below), market-anchored like football
   (order 18) and calibrated like basketball (`engine/nba_recal.py`).
3. Walk-forward backtest on 3+ seasons: fit only on data before each test fold, with a purge gap,
   scored against the closing price net of commission, every setting tried counted
   (deflated result). Written to `backtest/<SPORT>_STUDY.md`.
4. Shadow board from day 3: every fixture rated, every market on the full catalogue priced,
   paper bets placed by all three bots, graded nightly by the framework sweep.
5. Nightly retrain on the Oracle clock (`routines.TRAINING`), the daily health digest, the
   23:02 report and the sport-parity registry all carry the sport.
6. Gate report at the end of the week (#54 + Telegram): backtest return, closing-line value,
   shadow-week results, faults found.

**Week B: live.** Monday after the shadow week the sport goes live on all three bots wherever
the venue lists the market, **whatever the gate report says** (Architect: "a failing gate would
still go live"). Each sport has its own undo switch per bot. Markets and fixtures that are not
bet keep paper-trading and learning, as football does. The next sport starts its Week A the
same Monday.

## What every sport inherits (football + basketball, merged)

Scouts and the reasoning step, team news and line-ups (squad depth, not raw absences), the full
market catalogue (every option is a yes/no bet, both sides weighed), market-anchored chances and
calibration, closing-line value on every pick, the results loop and grading, automatic learning
per market family and league, the experiment engine, the self-improvement loop and R&D bot
issues, daily/weekly reporting, the WhatsApp mirror, and the three bots' unified rulebook
(staking as football; no steam). Football's football-only rules (goal models, draw guard,
FA Cup handicaps) map to the sport's own equivalent or are recorded `n/a` with the reason, the
same way `config/sport_parity.json` does for basketball.

**No steam betting on any new sport**, not even on paper.

## Calendar

Architect 2026-11-05 23:34: every sport's shadow (paper) practice runs from 5 Nov; **Amended 2026-11-06 00:01: every sport goes live on 12 Nov** ("they all go live next week").
Ice hockey: `engine/ice_hockey.py` (NHL goals model). Every other sport: `engine/multisport.py` (Matchbook
exchange fair price + an Elo model per sport learned from every finished Flashscore game).

| # | Sport | Shadow | Live from | Model planned (built today: hockey NHL goals model; every other sport Matchbook fair price + Elo) |
|---|---|---|---|---|
| 1 | Ice hockey (NHL, SHL, Liiga, NL, DEL, KHL) | 5-11 Nov | 12 Nov | Poisson/Dixon-Coles goals model (3-way 60 min + totals), starting goalie as the key input |
| 2 | American football (NFL, NCAAF, CFL) | from 5 Nov | 12 Nov | Efficiency ratings (EPA/play), spread/total like basketball handicaps |
| 3 | Snooker | from 5 Nov | 12 Nov | Player Elo + frame win rate, frame handicaps/totals |
| 4 | Darts | from 5 Nov | 12 Nov | Player ratings from three-dart average and checkout % |
| 5 | Volleyball / table tennis (no Setka Cup, TT Cup, Liga Pro, Elite Series) | from 5 Nov | 12 Nov | Set/point win-rate models |
| 6 | Cricket | from 5 Nov | 12 Nov | Ball-by-ball simulation by format |
| 7 | Rugby (union + league) | from 5 Nov | 12 Nov | Points model + ratings, handicaps/totals |
| 8 | Tennis (ATP, WTA, Challenger, ITF) | from 5 Nov | 12 Nov | Surface Elo + serve/return point model |
| 9 | Baseball (MLB, NPB, KBO, winter leagues) | from 5 Nov | 12 Nov | Starting-pitcher model (Statcast) |

Table tennis excludes leagues with known integrity problems (Setka Cup and similar).

## Honest limits

One shadow week is 30-100 bets: it proves the plumbing, not an edge. The backtest is the
evidence, and live grading continues to learn after go-live.
