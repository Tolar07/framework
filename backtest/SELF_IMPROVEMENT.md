# SELF-IMPROVEMENT REVIEW — 2026-10-30

Written weekly by `scripts/self_improve.py` (`self_improve.yml`): what the model uses, which learning loops produced tested evidence this week, and what to do better, ranked by expected value. The top open proposal is built record-only / shadow by the workflow's build job.

## (a) Inputs strong football models use

| input | value | status | where / evidence |
|---|---|---|---|
| team strength | 5 | LIVE | engine/dixon_coles.py; engine/elo.py; engine/calibration.py |
| xG for / against | 5 | TESTED | home win | xG edge: NO CLEAR EFFECT (Brier +0.00165); over 2.5 | xG total: NO CLEAR EFFECT (Brier +0.00103); BTTS yes | xG total: NO CLEAR EFFECT (Brier -0.00019) |
| recent form | 3 | TESTED | home win | form_ppg: HURTS (Brier -0.00039); home win | form_gd: HURTS (Brier -0.00042); home win | form_venue_ppg: NO CLEAR EFFECT (Brier -0.00019) |
| head-to-head | 1 | TESTED | home win | h2h_gd: NO CLEAR EFFECT (Brier -0.00020); home win | h2h_goals: HURTS (Brier -0.00022); over 2.5 | h2h_gd: NO CLEAR EFFECT (Brier -0.00032) |
| rest days / congestion | 2 | TESTED | backtest/REST_STUDY.md |
| travel distance | 1 | CONTEXT | engine/reasoning.py; engine/records/context_facts.py |
| lineups / injuries | 5 | CONTEXT | backtest/LINEUP_STUDY.md |
| motivation / table | 2 | CONTEXT | engine/reasoning.py; engine/records/context_facts.py; engine/form.py |
| referee | 1 | CONTEXT | engine/records/context_facts.py |
| weather | 1 | CONTEXT | engine/reasoning.py; engine/records/context_facts.py |
| market moves | 4 | TESTED | backtest/MATCHBOOK_PRICE_STUDY.md |

## (b) Learning loops this week

| loop | produced tested evidence | evidence |
|---|---|---|
| results learning | yes | newest evidence 2026-10-29 (1 d old) |
| match study | yes | newest evidence 2026-10-29 (1 d old) |
| why record | yes | newest evidence 2026-10-29 (1 d old) |
| tactics lessons | yes | 55 tested (no history 7 d back) |
| slip post-mortem | yes | 221 -> 360 tested over 7 d |
| why-weighted shadow | yes | 988 tested (no history 7 d back) |
| reasoning lessons | yes | newest evidence 2026-10-30 (0 d old) |
| experiment engine | yes | newest evidence 2026-10-30 (0 d old) |
| nightly refit | yes | newest evidence 2026-10-30 (0 d old) |

## (c) What to do better (by expected value)

1. **Model input: lineups / injuries (context)** (EV 3.5) — 'lineups / injuries' is read (engine/reasoning.py, engine/records/timing.py, engine/form.py) but never tested as a probability input. Build it as a feature (engine/inputs.py style, before-the-day only), add it to backtest/inputs_study.py and report Brier / log loss / CLV walk-forward.
2. **Model input: motivation / table (context)** (EV 1.4) — 'motivation / table' is read (engine/reasoning.py, engine/records/context_facts.py, engine/form.py) but never tested as a probability input. Build it as a feature (engine/inputs.py style, before-the-day only), add it to backtest/inputs_study.py and report Brier / log loss / CLV walk-forward.
3. **Model input: xG for / against (tested)** (EV 0.75) — 'xG for / against' was tested and is not a live probability input (home win | xG edge: NO CLEAR EFFECT (Brier +0.00165); over 2.5 | xG total: NO CLEAR EFFECT (Brier +0.00103)). Re-test when the data has grown; nothing to build now.
4. **Model input: travel distance (context)** (EV 0.7) — 'travel distance' is read (engine/reasoning.py, engine/records/context_facts.py) but never tested as a probability input. Build it as a feature (engine/inputs.py style, before-the-day only), add it to backtest/inputs_study.py and report Brier / log loss / CLV walk-forward.
5. **Model input: referee (context)** (EV 0.7) — 'referee' is read (engine/records/context_facts.py) but never tested as a probability input. Build it as a feature (engine/inputs.py style, before-the-day only), add it to backtest/inputs_study.py and report Brier / log loss / CLV walk-forward.
6. **Model input: weather (context)** (EV 0.7) — 'weather' is read (engine/reasoning.py, engine/records/context_facts.py) but never tested as a probability input. Build it as a feature (engine/inputs.py style, before-the-day only), add it to backtest/inputs_study.py and report Brier / log loss / CLV walk-forward.
7. **Model input: market moves (tested)** (EV 0.6) — 'market moves' was tested and is not a live probability input (backtest/MATCHBOOK_PRICE_STUDY.md). Re-test when the data has grown; nothing to build now.
8. **Model input: recent form (tested)** (EV 0.45) — 'recent form' was tested and is not a live probability input (home win | form_ppg: HURTS (Brier -0.00039); home win | form_gd: HURTS (Brier -0.00042)). Re-test when the data has grown; nothing to build now.
