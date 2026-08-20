# STATE.md — Daily Audit & Framework State

> **Daily fixture verification, outcome audit, and knowledge integration.**
> Updated each session with retrospective findings, calibration adjustments, and lessons learned.

---

## 2026-08-20 — Daily Retrospective Audit (Fixtures 2026-08-05 to 2026-08-09)

### Fixtures Audited
- **10 fixtures** across 10 dates (2026-08-05 → 2026-08-09)
- **23 settled legs** (from predictions table + legs table in brain/olp.db)
- **Engines evaluated**: consensus, bookmaker, dc, elo, cross, xg

### Hit Rate Summary

| Engine | Predictions | Settled | Hit Rate |
|--------|-------------|---------|----------|
| consensus | 1254 | 11 | **45.5%** |
| dc | 2694 | 14 | **42.9%** |
| elo | 1332 | 5 | **60.0%** |
| cross | 318 | 1 | 0.0% |
| bookmaker | 147 | 0 | — |
| xg | 48 | 0 | — |

**Overall**: 34.8% hit rate (8/23 legs correct)

---

### Calibration Audit — Probability Bin Analysis

| Prob Bin | Predictions | Hits | Hit Rate | Avg Prob | Calibration Error |
|----------|-------------|------|----------|----------|-------------------|
| 0.0–0.1 | 1 | 0 | 0.0% | 5.0% | -5.0pp |
| 0.1–0.2 | 2 | 0 | 0.0% | 15.0% | -15.0pp |
| **0.2–0.3** | **11** | **2** | **18.2%** | **24.4%** | **-6.2pp** |
| 0.3–0.4 | 4 | 2 | 50.0% | 35.0% | +15.0pp |
| 0.4–0.5 | 3 | 3 | 100.0% | 45.0% | +55.0pp |
| 0.5–0.6 | 2 | 1 | 50.0% | 55.0% | -5.0pp |
| 0.6–0.7 | 1 | 0 | 0.0% | 65.0% | -65.0pp |
| **0.8–0.9** | **2** | **0** | **0.0%** | **85.0%** | **-85.0pp** |

**Critical Findings:**
- **0.2–0.3 bin**: Model overconfident by ~6pp (18.2% actual vs 24.4% predicted) — 11 predictions, only 2 hits
- **0.8–0.9 bin**: **Severe overconfidence** — 0% hit rate vs 85% predicted (2 predictions, both misses)
- Model appears **miscalibrated at extremes** — both low-prob and high-prob predictions unreliable

---

### Miss Pattern Analysis

#### By League
| League | Misses | Total Legs | Miss Rate | Notes |
|--------|--------|------------|-----------|-------|
| Eredivisie | 8 | 8 | **100%** | All legs missed — systemic issue |
| Scottish Premiership | 5 | 5 | **100%** | All legs missed — systemic issue |
| Premier League | 1 | 1 | 100% | Small sample |
| La Liga | 0 | 0 | — | No settled legs |
| Champions League | 0 | 0 | — | No settled legs |

**Eredivisie & Scottish Premiership are critical problem leagues** — 13 combined misses with 0 hits. Recommend: flag for reduced weight or separate calibration track.

#### By Market
| Market | Misses | Hits | Hit Rate |
|--------|--------|------|----------|
| 1X2_HOME | 5 | 3 | 37.5% |
| 1X2_AWAY | 3 | 2 | 40.0% |
| 1X2_DRAW | 5 | 1 | **16.7%** |
| Over 1.5 | 2 | 0 | 0.0% |
| Over 2.5 | 2 | 1 | 33.3% |
| Under 2.5 | 0 | 1 | 100.0% |
| BTTS_Yes | 2 | 0 | 0.0% |
| Draw (Double Chance) | 1 | 0 | **0.0%** |

**Draw markets consistently missed** — 1X2_DRAW 16.7%, Double Chance Draw 0%. Model struggles with draw probability estimation.

#### By Engine (misses only)
| Engine | Misses |
|--------|--------|
| consensus | 6 |
| dc | 8 |
| elo | 2 |
| cross | 1 |

dc (Dixon-Coles) has highest miss count — expected given highest prediction volume.

---

### CLV (Closing Line Value) Analysis

- **Mean CLV**: -2.467% (17 legs with CLV captured)
- **Positive CLV legs**: 1 / 17
- **Gate status**: 17/30 legs, mean CLV negative → **Gate NOT met**
- **Architect signoff**: Active (ARCHITECT_SIGNOFF=1) — Phase 3 live capital deployed despite gate miss

**Interpretation**: Model edge is not materializing at closing line. The market is efficiently pricing against our predictions.

---

### Core Lessons Extracted

1. **Calibration drift at probability extremes** — The model is unreliable for both very low (<0.3) and very high (>0.8) probability predictions. These bins need either:
   - Separate calibration curves per bin
   - Temperature scaling post-processing
   - Exclusion from deployment until recalibrated

2. **Eredivisie & Scottish Premiership are untrustworthy** — 100% miss rate across 13 legs. Possible causes:
   - Insufficient historical depth for current season
   - Squad/manager changes not captured
   - Odds source quality issues for these leagues
   - **Action**: Downweight or quarantine these leagues in deployment

3. **Draw probability estimation is broken** — Consistent underperformance across 1X2_DRAW and Double Chance Draw markets. The Poisson/Dixon-Coles model structure may systematically misestimate draw probabilities.

4. **Negative mean CLV indicates no live edge** — Despite paper hit rates ~35-45%, the market closes against us. This suggests:
   - Model predictions are public/known (information leakage)
   - Odds movement is efficient against our signals
   - Deployment timing (entry price capture) may be suboptimal

5. **Engine consensus helps but not enough** — Consensus engine hit rate (45.5%) beats dc (42.9%), but both below 50%. Ensemble weighting (currently consensus=0.926, dc=0.926, elo=0.926) may need rebalancing toward elo (60% hit rate on small sample).

---

### Recommended Actions

| Priority | Action | Owner |
|----------|--------|-------|
| **P0** | Add calibration tracking per probability bin to daily monitoring | Data Quality Monitor |
| **P0** | Quarantine Eredivisie & Scottish Premiership from Acca A (deploy to singles only) | Bet Production (HR58) |
| **P1** | Investigate draw market model structure — consider separate draw probability model | Engine (dc/elo) |
| **P1** | Review odds capture timing — are we capturing entry prices at optimal moment? | CLV Logger |
| **P2** | Rebalance ensemble weights toward elo (higher hit rate) | Engine Config |
| **P2** | Add league-specific calibration curves (not global) | Recalibration Engine |

---

### Vault & Memory Sync

- **Canonical vault**: `olp_xdv_agent/olp_xdv/docs/obsidian-vault/`
- **Agent memory**: `.claude/projects/C--Users-Motunrayo-omniroute-test/memory/`
- **Sync status**: Pending (run `node scripts/vault-memory-sync.js` after this update)

---

## Framework Constants (Protected — Do Not Modify)

| Constant | Value | Source |
|----------|-------|--------|
| PHASE | 3 (live capital, Architect-deployed 2026-08-11) | `config.py` |
| ARCHITECT_SIGNOFF | 1 (override active) | `.env` |
| CLV Gate | 30 legs + positive mean CLV | `clv/phase3_gate.py` |
| Gate Status | 17/30 legs, mean CLV -2.467% → NOT MET | Board 2026-08-19 |
| Whitelist | 61 leagues (`config/leagues.json`) | ID401 |
| All Fixtures Eligible | YES (HR58, 2026-08-18) | `engine/leagues.py` |
| Odds Floor | 1.20 | `engine/acca.py` |
| Odds Preferred Ceiling | 1.50 | `engine/acca.py` |
| Odds Hard Cap | 2.00 | `engine/acca.py` + `engine/markets.py` |
| EDGE Formula | `model_prob × price − 1` | `engine/acca.py` |
| Markets Deployable | All (BLOCKED = {}) | ID405 override 2026-08-11 |

---

## Next Audit Target

**2026-08-21**: Fixtures from 2026-08-10 to 2026-08-14 (next 5-day window)

---

*Generated by daily retrospective audit workflow. Append new entries above this line.*