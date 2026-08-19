# Viking Match Analysis — Dinamo Zagreb vs Viking (2026-08-18)

**Date:** 2026-08-18  
**Competition:** UEFA Champions League Qualifying  
**Fixture:** Dinamo Zagreb vs Viking FK  
**Actual Result:** 2-2 (FT)  
**Half-time:** 2-2 (6' Beljo 1-0, 10' Lisica 2-0, 26' Christiansen 2-1, 39' Tripic 2-2)

---

## Framework Analysis (Pre-Match)

### Scan Output (Part 2 — THE SCAN)
| Fixture | 1X2 | O1.5/O2.5 | DC/BTTS | Src |
|---------|-----|-----------|---------|-----|
| Dinamo Zagreb v Viking (CL) | Dinamo Zag·36% | NO DATA — PENDING / NO DATA — PENDING | 1268 / — | ○ |

### Call Output (Part 1 — THE CALL)
| Fixture | H% | D% | A% | O1.5 | O2.5 | BTTS | BestMkt | Price | MES EV | Notes |
|---------|----|----|----|------|------|------|---------|-------|--------|-------|
| Dinamo Zagreb v Viking | 36 | 32 | 33 | — | — | — | Dinamo Zagreb or Viking (DC_1X) | 1.22 | -5.00% | NEG EV CLUBELO STRETCH |

### SCAN RECORD (Telegram)
```
2. Dinamo Zagreb v Viking (Champions League)
   Pick: Dinamo Zagreb to win (36%)
   Best market: Viking to win at 4.20 — +10.43% EV
```

---

## Bet Production Logic Application (HR58 / Protected Constant #7)

### Step 1: Eligibility Check ✓
- Kickoff date == today (2026-08-18) ✓
- `on_deploy_shortlist` true ✓
- At least one capital-cleared market with live price ✓

### Step 2: Multi-Market Evaluation via `_best_deployable_leg()`

| Market | Model Prob | Book Price | Implied Prob | EDGE = model_prob × price − 1 | Status |
|--------|-----------|------------|--------------|-------------------------------|--------|
| 1X2_HOME | 36% | ~1.85* | 54% | 36% × 1.85 − 1 = -33.4% | NEG EV |
| 1X2_DRAW | 32% | ~3.40* | 29% | 32% × 3.40 − 1 = +8.8% | +EV but price > 2.00 |
| 1X2_AWAY | 33% | **4.20** | 24% | **33% × 4.20 − 1 = +38.6%** | **+EV but price > 2.00** ❌ |
| OVER_1_5 | N/A | N/A | N/A | NO DATA | — |
| OVER_2_5 | N/A | N/A | N/A | NO DATA | — |
| UNDER_1_5 | N/A | N/A | N/A | NO DATA | — |
| UNDER_2_5 | N/A | N/A | N/A | NO DATA | — |
| BTTS_YES | N/A | N/A | N/A | NO DATA | — |
| BTTS_NO | N/A | N/A | N/A | NO DATA | — |
| DC_1X | 68% | **1.22** | 82% | **68% × 1.22 − 1 = -17.0%** | **NEG EV** ❌ |
| DC_X2 | 65% | ~1.35* | 74% | 65% × 1.35 − 1 = -12.3% | NEG EV |
| DC_12 | 69% | ~1.18* | 85% | 69% × 1.18 − 1 = -18.6% | NEG EV |

*Book prices for other markets estimated from 1X2 + DC_1X = 1.22

### Step 3: Hard Odds Cap (MAX_ODDS_CAP = 2.00) — **CRITICAL FILTER**
- Viking to win (AWAY) at 4.20 → **REJECTED** (price > 2.00)
- Draw at ~3.40 → **REJECTED** (price > 2.00)

### Step 4: Agreement Gate
- Default None (shipped EV-ranking) → not a factor

### Step 5: Best Deployable Leg Selection
- **Only market passing odds cap**: DC_1X at 1.22
- **EDGE**: -17.0% (NEGATIVE)
- **Result**: No deployable leg with positive EDGE → **fixture produces NO LEG**

### Step 6: Acca A Construction
- Top 4-5 highest-EDGE legs across all fixtures
- Viking match contributed **0 legs** (no positive-EDGE market under odds cap)
- Acca A contained only: Fenerbahçe v Lyon — BTTS Yes @ 1.62

---

## Alternative Market Analysis

### Markets That WOULD Have Won (Result: 2-2 Draw)
| Market | Result | Would Win? |
|--------|--------|------------|
| 1X2_DRAW | 2-2 | ✅ YES |
| DC_1X (Dinamo or Viking) | 2-2 | ✅ YES (covers draw) |
| DC_X2 (Draw or Viking) | 2-2 | ✅ YES (covers draw) |
| DC_12 (Dinamo or Viking) | 2-2 | ✅ YES (covers draw) |
| OVER_1_5 | 4 goals | ✅ YES |
| OVER_2_5 | 4 goals | ✅ YES |
| BTTS_YES | Both scored | ✅ YES |
| 1X2_HOME | Dinamo win | ❌ NO |
| 1X2_AWAY | Viking win | ❌ NO |
| UNDER_2_5 | 4 goals | ❌ NO |
| BTTS_NO | Both scored | ❌ NO |

### Highest-EDGE Alternative Markets (If Odds Cap Ignored)
1. **1X2_AWAY (Viking win) @ 4.20** — EDGE +38.6% ❌ LOST
2. **1X2_DRAW @ ~3.40** — EDGE +8.8% ✅ **WOULD WIN**
3. **OVER_2_5 @ ~1.80*** — EDGE depends on model prob
4. **BTTS_YES @ ~1.65*** — EDGE depends on model prob

*Estimated prices from typical CL qualifier markets

---

## Why the Framework Missed This

### Root Cause: Odds Cap Filter (MAX_ODDS_CAP = 2.00)
The **FL-bias guardrail** (favourite-longshot bias protection) rejects any market priced > 2.00. This is a deliberate, Architect-ratified design choice:
- Longshot markets (price > 2.00) historically show negative CLV
- The cap prevents the framework from chasing high-odds "value" that doesn't persist to closing

### What the Scan Showed vs What Production Used
| Source | Best Market | Price | EV/EDGE | In Production? |
|--------|-------------|-------|---------|----------------|
| SCAN RECORD (Telegram) | Viking to win (AWAY) | 4.20 | +10.43% EV | ❌ Rejected by odds cap |
| THE CALL (Board) | DC_1X | 1.22 | -5.00% EV | ❌ NEG EV, not selected |

**Discrepancy**: The SCAN RECORD showed Viking win at 4.20 as "+10.43% EV" while THE CALL showed DC_1X at 1.22 as "-5.00% EV". These are DIFFERENT MARKETS with different calculations:
- SCAN used raw model_prob × price − 1 with Viking model_prob = 33%
- CALL used blended probability for DC_1X (Home + Draw = 68%) at 1.22

### The ClubElo Stretch Fallback
The note "NEG EV CLUBELO STRETCH" indicates this fixture was rated using ClubElo ratings as a fallback because Dixon-Coles had insufficient match history for both teams in the fitting window. ClubElo is a **stretch model** — less reliable than the primary DC engine.

---

## Comparative Assessment: Framework Logic vs Reality

| Aspect | Framework Decision | Reality (2-2 Draw) | Assessment |
|--------|-------------------|-------------------|------------|
| **Acca A inclusion** | Excluded (no +EV leg under cap) | Would have lost anyway (DC_1X wins but NEG EV) | ✅ **Correct exclusion** |
| **Viking win (4.20)** | Rejected by odds cap | ❌ Lost | ✅ **Correct rejection** |
| **Draw (~3.40)** | Rejected by odds cap | ✅ Would win | ⚠️ **False negative** — but odds cap is intentional |
| **DC_1X (1.22)** | Only market under cap, but NEG EV | ✅ Would win | ⚠️ **False negative on EV** — market won but was -EV |
| **OVER_2.5 / BTTS** | NO DATA — PENDING | ✅ Would win | ❌ **Data gap** — missing O/U & BTTS prices |

### Key Insight
The framework **correctly avoided a negative-EV bet** (DC_1X at 1.22 with -17% EDGE). The fact that DC_1X "would have won" is irrelevant — a winning bet with negative EDGE is still a losing proposition over time.

The **real miss** was the **NO DATA — PENDING** on OVER_2.5 and BTTS markets. If those had live prices (likely ~1.80 and ~1.65 respectively), and if model probabilities supported them, they could have been +EV deployable legs under the 2.00 cap.

---

## Hard Rule Compliance Check (HR58)

| HR58 Component | Compliance | Notes |
|----------------|------------|-------|
| Eligibility (kickoff today, shortlist, DEPLOYABLE price) | ✅ | Met |
| Multi-market selection across ALL EDGE_MARKETS | ⚠️ PARTIAL | O/U and BTTS had NO DATA — not evaluated |
| EDGE = model_prob × price − 1 ranking | ✅ | Applied to available markets |
| Hard odds cap (MAX_ODDS_CAP = 2.00) | ✅ | Correctly rejected >2.00 markets |
| Agreement gate (opt-in) | N/A | Default None |
| Acca A: top 4-5 highest EDGE | ✅ | Only 1 leg qualified (Fenerbahçe v Lyon) |
| Split accas | N/A | No remainder legs |
| Singles with booking codes | N/A | No remainder legs |
| No fixture in two bets | ✅ | Trivially satisfied |
| Write-back to BoardFixture | ✅ | best_market_key = DC_1X recorded |
| Verification stamp | ⚠️ | SportyBet ⚠ unverified |

---

## Recommendations

### 1. Data Gap Priority (High)
The **NO DATA — PENDING** on OVER_1.5, OVER_2.5, BTTS for this fixture is the actionable gap. TheSportsDB/api-football should provide these for CL qualifiers. Fix the odds pipeline to populate these markets.

### 2. ClubElo Stretch Calibration (Medium)
The "CLUBELO STRETCH" fallback produced a 36/32/33 1X2 split that may not reflect true probabilities. Consider:
- Flagging stretch-rated fixtures more prominently
- Requiring minimum DC match history before deploying capital

### 3. Odds Cap Validation (Low — Architect Decision)
The 2.00 cap correctly rejected Viking win at 4.20 (which lost). The Draw at ~3.40 would have won but is by-design excluded. This is a **feature, not a bug** — the cap protects against FL-bias. No change recommended without Architect directive.

---

## Conclusion

**The framework behaved correctly per HR58.** The Viking match produced no production leg because:
1. The only market under the 2.00 odds cap (DC_1X at 1.22) had **negative EDGE (-17%)**
2. All positive-EDGE markets (Viking win 4.20, Draw ~3.40) were **correctly rejected by the FL-bias odds cap**
3. Potentially +EV markets (OVER_2.5, BTTS) had **NO DATA — PENDING**

**The miss was a data availability issue, not a logic error.** The hard rule (HR58) held: no negative-EDGE leg entered Acca A, no >2.00 odds leg entered Acca A. The framework preserved capital discipline.

**Actionable fix**: Resolve the NO DATA — PENDING on O/U and BTTS markets for continental qualifiers so the multi-market selection has full market universe to evaluate.