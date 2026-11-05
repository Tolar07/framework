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

| # | Sport | Shadow week | Live from | Model starting point |
|---|---|---|---|---|
| 1 | Ice hockey (NHL, SHL, Liiga, NL, DEL, KHL) | 9-15 Nov | 16 Nov | Poisson/Dixon-Coles goals model (3-way 60 min + totals), starting goalie as the key input |
| 2 | American football (NFL, NCAAF) | 16-22 Nov | 23 Nov | Efficiency ratings (EPA/play), spread/total like basketball handicaps |
| 3 | Snooker | 23-29 Nov | 30 Nov | Player Elo + frame win rate, frame handicaps/totals |
| 4 | Darts | 30 Nov-6 Dec | 7 Dec | Player ratings from three-dart average and checkout % |
| 5 | Volleyball / table tennis (WTT/ITTF only) | 7-13 Dec | 14 Dec | Set/point win-rate models |
| 6 | Cricket | 14-20 Dec | 21 Dec | Ball-by-ball simulation by format |
| 7 | Rugby | 21-27 Dec | 28 Dec | Points model + ratings, handicaps/totals |
| 8 | Tennis (ATP, WTA, Challenger, ITF) | 28 Dec-3 Jan | 4 Jan | Surface Elo + serve/return point model |
| 9 | Baseball (MLB, NPB, KBO) | 4-10 Jan (winter leagues) | MLB Opening Day | Starting-pitcher model (Statcast) |

Table tennis excludes leagues with known integrity problems (Setka Cup and similar).

## Honest limits

One shadow week is 30-100 bets: it proves the plumbing, not an edge. The backtest is the
evidence, and live grading continues to learn after go-live.
