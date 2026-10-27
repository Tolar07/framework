# Reasoning ideas audit — week-plan item 7 (2026-10-27)

What already exists on `main` (as of d9cc40cf) for each idea on the list. **Every new item starts RECORDED ONLY:**
it writes numbers to the picks/graded files and changes no stake, threshold, CLV gate, `ARCHITECT_SIGNOFF`
or protected file. Wiring one into stakes needs the Architect's OK after out-of-sample gains.

| # | Idea | Status | What is there / what is missing |
|---|---|---|---|
| 1 | Cross-market consistency (1X2 vs totals vs handicap) | **partial → built** | `engine/full_markets.market_matrix` fits independent Poisson to 1X2 + O/U 2.5 only, used by run_daily's LINE CONSISTENCY GUARD to *drop* stale lines. Missing: every O/U line + BTTS, rho, both sides, recorded and measured. Built: `engine/market_consistency.py` (joint Dixon-Coles fit, ev per side for main markets and handicap/ladder lines), recorded on every graded universe game (`row["xm"]`), measured in `backtest/MARKET_CONSISTENCY_STUDY.md`. |
| 2 | Bias checks on graded data (fav-longshot, public teams, tipster legs < 1.30) | partial | Fav-longshot read in `backtest/clv_backtest.py`, the both-sides/universe studies, and tipster leg study (memory: sub-1.30 legs underperform). No public-team check; nothing recorded per pick. |
| 3 | Timing: after line-ups, steam, reverse line moves | partial | Line-up pass (#186, `lineup_check` on singles, `backtest/lineup_study.py`); drift fields on singles (`drift_pct`, `drift_since_board`); steam driven by the live loop in sportybet-agent #17. No reverse-line-move signal (price moving against the public side); no measured "bet after line-ups" timing rule. |
| 4 | Context checklist as structured facts (source, direction, size) | partial | `engine/cognitive_core.detect_regime_flags`: short rest, FIFA window, cup rotation, team news level, Elo/DC divergence. Flags only, no source/direction/size. Missing: travel, motivation, weather, referee, new manager, derby. |
| 5 | Correlation-aware accas + per-night exposure/correlation caps | partial | `engine/clv_accas.py` builds accas; Dixon-Coles models within-game score correlation. No cross-leg correlation estimate and no per-night exposure cap. |
| 6 | Kelly shrunk by model disagreement | missing | `engine/staking.py` stakes by tier ROI; no Kelly fraction and no disagreement shrinkage (stakes are protected; record a shadow fraction only). |
| 7 | Model ensemble (DC, Elo, xG, market), out-of-sample weights | partial | Separate models exist (`dixon_coles.py`, `elo.py`, `xg_model.py`, `sharp_p` market); `engine/retrain.py` refits per-family calibration on a holdout. No learned blend weights across the models. |
| 8 | Devil's-advocate / pre-mortem by a second model | exists | Cognitive core red-team debate + post-mortems (#183), free-model verdict panel (#186). |
| 9 | Drift detection per family | partial | `retrain.py` per-family holdout refit; `backtest/metrics_history.py` history. No alarm when a family's calibration or CLV breaks (CUSUM / rolling Brier). |
| 10 | Price shopping Matchbook vs SportyBet | partial | `sharp_p` (Matchbook de-margined) is on every single and drives `sharp_ev`; no "better price at the other book" record per pick. |

## Order of work (missing/partial, by expected value)

1. **Cross-market consistency** — built, recorded only. First out-of-sample read (5,067 games, later half from 17 Oct): sides the grid calls soft (gap > +1%, chosen on the earlier half) lose −6.0% vs −13.2% for the other side of the same lines, but inside the 1.20–2.00 band they match every side (−6.9% vs −6.8%, CLV −7.5% vs −7.7%). That is favourite-longshot composition, not an edge. **No case for stakes.** Keep recording; re-read once the live `xm` field has the last look and Matchbook closing to compare.
2. Bias checks recorded per pick (fav-longshot band, tipster-leg band) — next.
3. Reverse-line-move / timing record.
4. Context facts with source/direction/size.
5. Cross-leg correlation + nightly exposure record for accas.
6. Shadow Kelly fraction shrunk by DC/Elo/market disagreement.
7. Out-of-sample ensemble weights.
8. Per-family drift alarm.
9. Cross-book price record.
