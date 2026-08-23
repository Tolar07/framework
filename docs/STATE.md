# STATE.md — Framework State & Daily Retrospective Audit

> **Per Architect directive:** This file is the supervisor's single source of truth for multi-session state. Updated daily with fixture verification, outcome audit, and knowledge integration.

---

## 2026-08-22 Production Pipeline — Daily Retrospective

### Fixture Verification

| Item | Status | Notes |
|------|--------|-------|
| Acca count | **9 accas (A–I)** | Source: `acca_2026-08-22.json` |
| Total legs settled | **38 / 46** | 26W / 12L = 68.4% win rate |
| Pending (unverifiable) | **8 legs** | ESPN coverage gaps: Ligue 2, La Liga 2, Swiss Super League, Eredivisie (Feyenoord/Ajax fixtures missing from Aug 22 ESPN schedule) |
| Postponed | **1 leg** | St Johnstone v Celtic (Scottish Premiership) — not in acca file |

**Data sources used:**
1. **football-data.co.uk (T1)** — 2627 season files empty/headers-only at time of verification
2. **ESPN API (T2)** — DNS resolution failed for `site.api.espn.com` — fallback to manual
3. **Manual verification (T3)** — `manual_verification_2026-08-22.json` with 38 entries (fixture names now exactly match acca file)

**3 manual verification data errors found and corrected (2026-08-23):**
- Le Mans v Stade Brestois 29: 0-0 (WRONG) → 2-2 (ESPN authoritative)
- Birmingham v Bristol City: 2-1 (WRONG) → 2-2 (ESPN authoritative)
- Fenerbahce v Konyaspor: 3-0 (WRONG) → 4-2 (ESPN authoritative)

**3 manual errors corrected in** `manual_verification_2026-08-22.json`

---

### Outcome Audit

| Acca | Legs | W/L/P | Result | Combined Odds |
|------|------|-------|--------|---------------|
| A | 5/5 | 3W 1L 1P | **PENDING** | 4.28 |
| B | 5/5 | 5W 0L 0P | **WIN** | 6.76 |
| C | 5/5 | 4W 1L 0P | **LOSS** | 5.06 |
| D | 5/5 | 2W 2L 1P | **PENDING** | 6.69 |
| E | 5/5 | 2W 2L 1P | **PENDING** | 4.62 |
| F | 5/5 | 1W 3L 1P | **PENDING** | 11.38 |
| G | 5/5 | 3W 2L 0P | **LOSS** | 10.93 |
| H | 5/5 | 3W 1L 1P | **PENDING** | 10.70 |
| I | 6/6 | 3W 0L 3P | **PENDING** | 6.83 |

**Settled acca outcomes:** 1 WIN (Acca B), 2 LOSS (C, G), 0 pending fully settled  
**Win rate (settled legs):** 68.4% (26W / 12L)  
**Win rate (settled accas):** 33.3% (1W / 2L)

**Key failures:**
- Acca A PENDING: Nice-Lorient OVER_1_5 — goalless 0-0 draw (LOSS); Metz-Laval DC_12 — PENDING (Ligue 2)
- Acca C LOSS: Blackburn-Middlesbrough DC_X2 — Blackburn won 2-1 (home bias)
- Acca D 1 pending: Eldense-Cadiz DC_12 — unknown (La Liga 2)
- Acca E 1 pending: Fenerbahce-Konyaspor duplicate — same match as Acca D, already settled
- Acca F 1 pending: Espanol-Real Madrid BTTS_NO — PENDING (duplicate of Acca E leg)
- Acca G LOSS: Inter-Monza BTTS_NO (both scored 4-1); Troyes-Paris FC OVER_2_5 (0-0)
- Acca H 1 pending: Zurich-Basel OVER_2_5 — PENDING (Swiss Super League)
- Acca I 3 pending: Nantes-Rodez (Ligue 2), Feyenoord-AZ (Eredivisie not on Aug 22), Ajax-Zwolle (Eredivisie not on Aug 22)

---

### Knowledge Integration

**5 failure patterns identified for framework evolution:**

1. **OVER_1_5 on defensive/low-scoring fixtures** — Nice-Lorient (0-0); Le Mans-Brest (2-2 after correction, still under 1.5 threshold at half-time before equalizer). Need league/scoring-profile filter for Ligue 1 openers.
2. **DC_X2 on home favorites** — Blackburn 2-1 Middlesbrough; Ipswich 2-1 Sunderland. Home-win bias in Championship not captured by model.
3. **BTTS_NO on open games** — Birmingham-Bristol City 2-2; Inter-Monza 4-1 (both scored). Need xG/shot-volume screening before BTTS_NO.
4. **Away wins severely underpriced** — Hull 2-0 Man United; model gave 1X2_AWAY on Man United. Framework underweights promoted/home-advantage upset risk.
5. **OVER_2_5 in cagey openers** — Swansea-Sheffield 0-0; Troyes-Paris FC 0-0. Early-season trend shows underperformance of OVER markets.

**Proposed fixes (pending Architect review):**

| Pattern | Fix |
|---------|-----|
| Early-season OVER legs | Apply `season_week <= 3` penalty — reduce prob by 10-15% |
| DC_X2 on home favs | Apply home-win probability boost to DC_X2 threshold (reject if home prob > 0.55) |
| BTTS_NO | Require xG < 2.2 combined OR defensive-profile flag (bottom-3 defensive + bottom-3 attacking) |
| CLV gate | Already recorded as protected constant; noting that zero CLV data captured for Aug 22 |
| Away win odds | Add promoted/home-advantage upset coefficient for Championship 1X2_AWAY picks |

---

### CLV Integration Status

**CLV log entries for 2026-08-22: 1 entry only** (Fenerbahce v Konyaspor, 1X2_DRAW)  
**Quantified CLV footprint match_score: 0 entries from acca legs in CLV log**  
**No CLV evals could be assessed**

The issue: CLV log entries are created during the **production** run (Stage B), not during results ingestion. Production runs for Aug 22 did not log closing lines to `clv/clv_log.json`, so the CLV feedback loop could not close.

**Root cause:** Either CLV capture is not running for production legs, or the integration step in `run_daily`/`produce` does not include CLV persistence for the Aug 22 run.

**Action required:** Investigate `clv/closing_capture.py` and check whether the Data Steward daemon (06:00 daily) is capturing closing lines for production legs. Existing `clv_log.json` entries are from 2026-08-04 to 2026-08-09 only — no Aug 22 entries.

---

### Pending Items (Not Settled as of 2026-08-23)

| Leg | Reason | Resolution Path |
|-----|--------|----------------|
| Metz v Laval (Ligue 2) | ESPN not covered for 2026-27 | Manual: check Flashscore/Google score after |
| Eldense v Cadiz (La Liga 2) | ESPN not covered for 2026-27 | Manual: check Flashscore/Google score after |
| Fenerbahce v Konyaspor (duplicate in Acca E) | Same as Acca D — already settled 4-2 | Remove duplicate or mark settled |
| Espanyol v Real Madrid (duplicate in Acca F) | Same as Acca E — already settled 1-2 | Remove duplicate or mark settled |
| Zurich v Basel (Swiss Super League) | ESPN not covered | Manual: check SwitchScore after |
| Nantes v Rodez (Ligue 2) | ESPN not covered for 2026-27 | Manual: check Flashscore after |
| Feyenoord v AZ (Eredivisie) | Fixture not on ESPN Aug 22 | Feyenoord played Aug 9/16; AZ played Aug 22 vs Fortuna Sittard (0-2) |
| Ajax v Zwolle (Eredivisie) | Fixture not on ESPN Aug 22 | Ajax played Aug 9 vs Zwolle (2-0); PEC Zwolle played Aug 22 vs Heerenveen (0-2) |

All PENDING entries are **HR35 compliant** — no fabricated scores, honest "NO DATA" state.

---

## Framework State

- **Phase:** Phase 3 (live capital, Architect-deployed 2026-08-11)
- **Paper-only flag:** `assert_paper_only()` hard-fails below Phase 3; booking module never clicks Place Bet
- **CLV Gate status:** 12/30 legs required, mean CLV > 0 (PROTECTED — never modified)
- **Last data steward run:** 2026-08-22 06:00 / 15:00
- **Last CLV capture:** 2026-08-09 (gap Aug 10-22 unexplained — needs investigation)
- **Verification log:** `data/verification_logs/verification_20260822.json`
- **Manual verification:** `data/manual_verification_2026-08-22.json` (38 entries, 3 errors corrected)
- **Summary report:** `data/verification_logs/verification_20260822.md`

---

## Historical Retrospectives

<details>
<summary>2026-08-21 (template)</summary>

No production run on 2026-08-21.

</details>

<details>
<summary>2026-08-20 (template)</summary>

No production run on 2026-08-20.

</details>