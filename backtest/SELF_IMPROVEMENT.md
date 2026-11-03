# SELF-IMPROVEMENT REVIEW — 2026-11-03

Written weekly by `scripts/self_improve.py` (`self_improve.yml`): what the model uses, which learning loops produced tested evidence this week, and what to do better, ranked by expected value. The top open proposal is built record-only / shadow by the workflow's build job.

## (a) Inputs strong football models use

| input | value | status | where / evidence |
|---|---|---|---|
| team strength | 5 | LIVE | engine/dixon_coles.py; engine/elo.py; engine/calibration.py |
| xG for / against | 5 | TESTED | home win | xG edge: NO CLEAR EFFECT (Brier +0.00147); over 2.5 | xG total: NO CLEAR EFFECT (Brier -0.00025); BTTS yes | xG total: NO CLEAR EFFECT (Brier -0.00022) |
| recent form | 3 | TESTED | home win | form_ppg: HURTS (Brier -0.00038); home win | form_gd: HURTS (Brier -0.00042); home win | form_venue_ppg: HURTS (Brier -0.00020) |
| head-to-head | 1 | TESTED | home win | h2h_gd: NO CLEAR EFFECT (Brier -0.00019); home win | h2h_goals: HURTS (Brier -0.00022); over 2.5 | h2h_gd: NO CLEAR EFFECT (Brier -0.00029) |
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
| results learning | yes | newest evidence 2026-11-02 (1 d old) |
| match study | yes | newest evidence 2026-11-02 (1 d old) |
| why record | yes | newest evidence 2026-11-02 (1 d old) |
| tactics lessons | yes | 0 -> 106 tested over 7 d |
| slip post-mortem | yes | 306 -> 431 tested over 7 d |
| why-weighted shadow | yes | 1161 tested (no history 7 d back) |
| reasoning lessons | yes | newest evidence 2026-11-03 (0 d old) |
| experiment engine | yes | newest evidence 2026-11-03 (0 d old) |
| nightly refit | yes | newest evidence 2026-11-03 (0 d old) |
| AI fact sheet | yes | newest evidence 2026-11-02 (1 d old) |
| verdict panel | yes | 127 tested (no history 7 d back) |
| learned weights | yes | newest evidence 2026-11-03 (0 d old) |
| prompt contest | yes | newest evidence 2026-11-01 (2 d old) |
| AI weekly review | yes | newest evidence 2026-11-02 (1 d old) |
| universe sweep | yes | newest evidence 2026-11-03 (0 d old) |
| paper book | yes | newest evidence 2026-11-03 (0 d old) |
| sharp list | yes | newest evidence 2026-11-03 (0 d old) |
| research runner | yes | newest evidence 2026-11-02 (1 d old) |
| matchbook ledger | yes | newest evidence 2026-11-03 (0 d old) |
| bot challengers | yes | newest evidence 2026-11-01 (2 d old) |

## (c) What to do better (by expected value)

1. **Model input proven: H003 — wire it in as a shadow feature** (EV 3.5) — research/runner.py accepted H003: SportyBet's closing Over 2.5 price knows something the model doesn't — lean the model's Over 2.5 toward it (evidence {'brier_model': 0.2429, 'gain': 0.0038, 'last_coef': 0.239, 'rows': 785, 'scored': 658, 'se': 0.00165, 'verdict': 'ADDS INFORMATION'}). Nothing consumes candidate features yet: build it as a model input in SHADOW (engine/inputs.py style), add it to engine/learned_weights.py and report walk-forward Brier / CLV. Promotion to the live model stays with the Architect.
2. **Model input: lineups / injuries (context)** (EV 3.5) — 'lineups / injuries' is read (engine/reasoning.py, engine/records/timing.py, engine/form.py) but never tested as a probability input. Build it as a feature (engine/inputs.py style, before-the-day only), add it to backtest/inputs_study.py and report Brier / log loss / CLV walk-forward.
3. **Model input: motivation / table (context)** (EV 1.4) — 'motivation / table' is read (engine/reasoning.py, engine/records/context_facts.py, engine/form.py) but never tested as a probability input. Build it as a feature (engine/inputs.py style, before-the-day only), add it to backtest/inputs_study.py and report Brier / log loss / CLV walk-forward.
4. **Model input: xG for / against (tested)** (EV 0.75) — 'xG for / against' was tested and is not a live probability input (home win | xG edge: NO CLEAR EFFECT (Brier +0.00147); over 2.5 | xG total: NO CLEAR EFFECT (Brier -0.00025)). Re-test when the data has grown; nothing to build now.
5. **Model input: travel distance (context)** (EV 0.7) — 'travel distance' is read (engine/reasoning.py, engine/records/context_facts.py) but never tested as a probability input. Build it as a feature (engine/inputs.py style, before-the-day only), add it to backtest/inputs_study.py and report Brier / log loss / CLV walk-forward.
6. **Model input: referee (context)** (EV 0.7) — 'referee' is read (engine/records/context_facts.py) but never tested as a probability input. Build it as a feature (engine/inputs.py style, before-the-day only), add it to backtest/inputs_study.py and report Brier / log loss / CLV walk-forward.
7. **Model input: weather (context)** (EV 0.7) — 'weather' is read (engine/reasoning.py, engine/records/context_facts.py) but never tested as a probability input. Build it as a feature (engine/inputs.py style, before-the-day only), add it to backtest/inputs_study.py and report Brier / log loss / CLV walk-forward.
8. **Model input: market moves (tested)** (EV 0.6) — 'market moves' was tested and is not a live probability input (backtest/MATCHBOOK_PRICE_STUDY.md). Re-test when the data has grown; nothing to build now.
9. **Model input: recent form (tested)** (EV 0.45) — 'recent form' was tested and is not a live probability input (home win | form_ppg: HURTS (Brier -0.00038); home win | form_gd: HURTS (Brier -0.00042)). Re-test when the data has grown; nothing to build now.
