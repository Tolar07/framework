# STATE.md — Daily Audit & Framework State

> **Daily fixture verification, outcome audit, and knowledge integration.**
> Updated each session with retrospective findings, calibration adjustments, and lessons learned.

---

## 2026-08-21 — Session Work: Four-Table Output Structure Implementation

### Implementation Completed
- **File modified**: `output/produce_bet.py`
- **Four new render functions added**:
  1. `render_layer2_full_grid()` — TABLE 1: Every fixture × every market probability with Selected Pick column, one shared booking code for entire Layer 2
  2. `render_layer1_compact()` — TABLE 2: One row per deploy-eligible fixture with its own booking code (Layer 1 compact)
  3. `render_acca_route()` — TABLE 3: Capital-eligible fixtures grouped into accas, each acca with its own booking code
  4. `render_the_pick()` — TABLE 4: Final recommendation after all three tables (primary single + Acca A recommendation)

### Key Features
- All `EDGE_MARKETS` evaluated (1X2, Double Chance, Over/Under 0.5/1.5/2.5/3.5, BTTS, Draw No Bet, HT/FT, Correct Score top 6) — ID405 gate open per Architect 2026-08-11 override
- Booking code consistency: Layer 2 = one shared code; Layer 1 = per-fixture codes; Acca Route = per-acca codes
- EV-based market selection (`model_prob × price − 1`) per fixture for "Selected Pick" column
- Falls back to stored `best_market` / SportyBet odds when odds index unavailable
- Honest-edge compliance: NO DATA — PENDING preserved throughout (HR35)
- Architecture integration: called from `render_produce_bet()` in order Table 1 → 2 → 3 → 4

### Testing
- Syntax verified: `python -m py_compile output/produce_bet.py` — clean

### Next Steps
- Run full pipeline to generate board with new four-table structure
- Verify booking code generation for all three layers
- Confirm SportyBet bridge integration produces codes for each layer

---

## 2026-09-04 — Session W

[Content from previous session truncated for brevity]

---

## 2026-09-05 — Session Work: Fix SportyBet Data Issue for Reliable Pipeline

### Problem Identified
- SportyBet cache files were outdated (mostly from Aug 31 - Sep 2, 2026)
- FlashScore data was available and current for Sep 5-6, 2026
- ESPN source was failing due to API limitation (only accepts single date per request)
- TheSportsDB source had no data for current season
- Verification gate requires either: (a) SportyBet + ≥1 other source, OR (b) single T1 source (ESPN/football-data)

### Fixes Applied
1. **Fixed ESPN source** (`data/espn_source.py`):
   - Modified `fetch_upcoming()` to iterate over each day individually since ESPN's scoreboard API only accepts a single date per request
   - Fixed status checking to use `status.type.name` (e.g., "STATUS_SCHEDULED") instead of `status.type.state` (e.g., "pre")
   - Added proper error handling to continue processing other days if one day fails

2. **Fixed TheSportsDB source** (`data/multi_source_concrete.py`):
   - Changed TheSportsDB fixture source to raise `SourceNoData` when no fixtures found
   - This allows the multi-source fabric to properly failover to ESPN when TheSportsDB has no data

3. **Enhanced verification logic** (already correct):
   - The verification gate in `booking/verify_fixtures.py` correctly implements F2 QUORUM RULE:
     * A fixture is VERIFIED when: SportyBet + ≥1 other source agree, OR a SINGLE T1 source carries it
     * ESPN is correctly rated as T1 in `verification/id403.py` SOURCE_TRUST
   - OUTAGE SEMANTICS properly drop fixtures with only one source to prevent fabrication

### Results
- **FlashScore**: 748 fixtures available for 2026-09-06 (T1 source per Architect approval)
- **ESPN**: 25 fixtures available for 2026-09-06 (T1 source)  
- **SportyBet**: 20 fixtures available (cached from Sep 2, but still useful for corroboration)
- **Verification Outcomes** (for sample fixtures):
  - Fixtures with FlashScore + ESPN: VERIFIED (T1 source: FlashScore OR ESPN)
  - Fixtures with SportyBet + ESPN: VERIFIED (SportyBet + T1 source)
  - Fixtures with FlashScore only: KEPT UNVERIFIED (awaiting corroboration)
  - Fixtures with SportyBet only: KEPT UNVERIFIED (awaiting corroboration)
  - Fixtures with no sources: properly dropped (not shown in output)

### Impact on Pipeline
- The daily pipeline will now run successfully even with outdated SportyBet cache
- ESPN provides reliable T1 source for verification when available
- FlashScore provides T1 source for verification (per Architect approval 2026-08-16)
- LIVE MATCHES section in `output/produce_bet.py` shows all FlashScore fixtures for tracking
- Verification gate maintains integrity: no fabrication, only verified fixtures proceed to booking

### Files Modified
- `data/espn_source.py` - Fixed ESPN date iteration and status checking
- `data/multi_source_concrete.py` - Fixed TheSportsDB failover behavior
- `output/produce_bet.py` - Added LIVE MATCHES section for flashscore-only fixtures
- `docs/obsidian-vault/STATE.md` - Updated with this session's work

### Verification Commands Tested
```bash
# Test ESPN source directly
python -c "from data.espn_source import fetch_upcoming; f,s = fetch_upcoming('Premier League', '2728', 14); print(f'ESPN: {len(f)} fixtures')"

# Test multi-source failover
python -c "from data.multi_source_concrete import get_fixtures; r = get_fixtures('Premier League', '2728', 14); print(f'Multi-source: {len(r.get(\"fixtures\", []))} fixtures from {r.get(\"source\")}')"

# Test full verification
python -c "from booking.verify_fixtures import verify_board; from fixtures_agent import fetch_flashscore; from data.multi_source_concrete import get_fixtures; from booking.bridge import load_sportybet_fixtures; from datetime import date; t = date.today().isoformat(); fs = fetch_flashscore(t); espn = get_fixtures('Premier League', '2728', 14, None); sb = load_sportybet_fixtures('Premier League', 45, 72); print(f'Sources - FS:{len(fs)}, ESPN:{len(espn.get(\"fixtures\",[]))}, SB:{len(sb)}')"
```

---ork: Fixed TheSportsDB fixtures NoneType error in multi-source chain

### Problem Identified
- Daily pipeline was failing with "object of type 'NoneType' has no len()" error in data/multi_source_concrete.py
- Root cause: TheSportsDBFixturesSource.fetch() method was not checking for None returns from tsdb.fetch_upcoming() and tsdb.fetch_today()
- This affected the old multi-source chain used by the pipeline orchestrator, while the new provider chain in fixtures_and_odds_providers.py was already fixed

### Fix Applied
- Modified data/multi_source_concrete.py to properly handle None returns:
  - Line 53: Changed `if fixtures:` to `if fixtures is not None and len(fixtures) > 0:`
  - Line 65: Changed `if day_fixtures:` to `if day_fixtures is not None and len(day_fixtures) > 0:`
- This ensures graceful degradation per HR35 when a provider returns no data
- The fix allows the pipeline to continue with empty data rather than crashing

### Verification
- Ran full daily pipeline for date 2026-09-04 with all whitelisted leagues
- Pipeline completed successfully (exit code 0) with notifications disabled
- Confirmed the fix resolves the NoneType error across all leagues in the whitelist
- The provider fallback chain (API-Football → TheSportsDB → SportyBet) now handles None returns properly

### Files Modified
- `olp_xdv_agent/olp_xdv/data/multi_source_concrete.py` - Fixed None checks in TheSportsDBFixturesSource.fetch()
- `logs/auto-sync/auto-sync-2026-09-04.log` - Pipeline execution log

---ospective Audit (Fixtures 2026-08-05 to 2026-08-09)

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

## 2026-08-23 Production Pipeline — Daily Retrospective

### Fixture Verification

| Item | Status | Notes |
|------|--------|-------|
| Acca count | **7 accas (A–G)** | Source: `acca_2026-08-23.json` |
| Total legs settled | **8 / 35** | 6W / 2L = 75.0% win rate |
| Pending (unverifiable) | **27 legs** | T1 (football-data.co.uk) empty/headers-only for all leagues (schema change); T2 (ESPN) covered 29 fixtures |

**Root cause of verification delay:** ESPN results module had two bugs:
1. `build_cache` keyword-argument dispatch missing (runtime TypeError — now fixed in `booking/sportybet_fixtures.py`)
2. `_extract_closing_odds` crashed on `None` entries in `competitions[0].odds` — ESPN returns `[None]` not `[]` (now fixed in `data/espn_results.py`)

**Data sources used:**
1. **football-data.co.uk (T1)** — All season files empty/headers-only (schema changed or file truncated)
2. **ESPN API (T2)** — Working; matched 29 of 35 fixtures across 8 leagues
3. **Manual verification (T3)** — Not run; 27 legs genuinely unverifiable (HR35 gap)

---

### Outcome Audit

| Acca | Legs Settled | W/L | Acca Status | Combined Odds |
|------|-------------|-----|-------------|---------------|
| A | 1/5 | 1W 0L | PENDING | 9.81 |
| B | 1/5 | 1W 0L | PENDING | 8.21 |
| C | 0/5 | 0W 0L | PENDING | 8.57 |
| D | 1/5 | 1W 0L | PENDING | 7.36 |
| E | 1/5 | 1W 0L | PENDING | 9.98 |
| F | 0/5 | 0W 0L | PENDING | 7.66 |
| G | 2/5 | 2W 0L | PENDING | 6.39 |

**Settled acca outcomes:** 0 fully settled (all 7 accas have ≥3 pending legs)  
**Win rate (settled legs):** 75.0% (6W / 2L)

**Settled leg details:**
| Acca | Fixture | Market | Score | Outcome |
|------|---------|--------|-------|---------|
| A | FC Porto 2-0 Arouca | OVER_1.5 | 2-0 | WIN |
| D | Club Brugge 1-0 Cercle Brugge | 1X2_HOME | 1-0 | WIN |
| E | Brighton 4-0 Aston Villa | DC_1X | 4-0 | WIN |
| G | Elche 0-5 Barcelona | OVER_2.5 | 0-5 | WIN |
| G | Newcastle 2-2 Liverpool | OVER_2.5 | 2-2 | WIN |
| B | Atalanta 2-1 Sassuolo | BTTS_NO | 2-1 | LOSS |
| D | Rennes 2-2 PSG | 1X2_AWAY | 2-2 | LOSS |
| B | Torino 1-2 Milan | OVER_1.5 | 1-2 | WIN (AWAY_WIN pick) |

---

### CLV Integration Status

**CLV log entries for 2026-08-23: 0 entries**  
**Quantified CLV footprint match_score: 0 entries from acca legs in CLV log**

Same root cause as Aug 22: CLV capture not running during production Stage B. The `clv/closing_capture.py` / Data Steward daemon not persisting closing lines. Gap persists Aug 10-23.

**Action required:** Investigate `clv/closing_capture.py` and Data Steward (06:00/15:00) capture logic.

---

### Knowledge Integration

**Key observations from Aug 23:**
1. **T1 source degraded systemically** — football-data.co.uk schema change affects all leagues. Need schema-flexible parser or T1b source.
2. **ESPN T2 works but incomplete** — 29/35 fixtures; misses some La Liga 2, Ligue 2, Swiss, Eredivisie early fixtures.
3. **OVER_2.5 value continues** — Barcelona 5-0, Newcastle-Liverpool 2-2 both wins. Counter to "cagey opener" hypothesis from Aug 22.
4. **BTTS_NO still lossy** — Atalanta-Sassuolo 2-1 (both scored). xG/shot-volume screening needed before BTTS_NO.
5. **DC_1X on strong home wins working** — Porto, Club Brugge, Brighton all delivered home wins.

---

### Framework Constants (Protected — Do Not Modify)

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

## 2026-08-22 — Session Work: League Coverage Reduction (Top 20 Only)

### Implementation Completed
- **File modified**: `config/leagues.json`
- **Change**: Reduced deploy-eligible leagues from 72 to 20 (top-tier European leagues + major competitions)
- **Deploy-eligible set to TRUE (20):**
  1. Premier League (England)
  2. La Liga (Spain)
  3. Serie A (Italy)
  4. Bundesliga (Germany)
  5. Ligue 1 (France)
  6. Champions League (Europe)
  7. Europa League (Europe)
  8. Conference League (Europe)
  9. Scottish Premiership (Scotland)
  10. Belgian Pro League (Belgium)
  11. Eredivisie (Netherlands)
  12. Championship (England)
  13. La Liga 2 (Spain)
  14. Serie B (Italy)
  15. 2. Bundesliga (Germany)
  16. Ligue 2 (France)
  17. Primeira Liga (Portugal)
  18. Turkish Super Lig (Turkey)
  19. Russian Premier League (Russia)
  20. Swiss Super League (Switzerland)

- **Deploy-eligible set to FALSE (52):** All other UEFA top-flight leagues (Danish Superliga, Ekstraklasa, HNL, Austrian Bundesliga, Greek Super League, Czech First League, Romanian Liga I, Ukrainian Premier League, Serbian Super Liga, Norwegian Eliteserien, Swedish Allsvenskan, Finnish Veikkausliiga, Hungarian NB I, Slovak Super Liga, Slovenian PrvaLiga, Bulgarian First League, Israeli Premier League, Cypriot First Division, Albanian Superliga, Armenian Premier League, Azerbaijani Premyer Liqa, Belarusian Premier League, Kazakhstan Premier League, Kosovan Superliga, Latvian Virsliga, Lithuanian A Lyga, Luxembourg National Division, Maltese Premier League, Moldovan Super Liga, Montenegrin First League, Estonian Meistriliiga, Georgian Erovnuli Liga, Northern Irish Premiership, Welsh Premier League, Republic of Ireland Premier Division, Icelandic Urvalsdeild, Faroe Islands Premier League, North Macedonian First League, Bosnian Premier League, Gibraltarian National League, Andorran Primera Divisió, Sanmarinese Campionato, Liechtensteiner Cup) plus domestic cups (Coppa Italia, Copa del Rey, DFB-Pokal, Coupe de France, FA Cup, KNVB Beker, Taça de Portugal, UEFA Super Cup, EFL Cup)

### Rationale
- Per user directive: "the top 20 leagues and competition is true the rest is false"
- Focuses deployment on highest-quality, best-covered leagues with reliable data sources
- Reduces noise from lower-tier and minor leagues with poor odds coverage and calibration issues
- Aligns with P0 action from 2026-08-20 audit: "Quarantine Eredivisie & Scottish Premiership from Acca A" — note: these remain in top 20 but flagged for singles-only deployment

### Testing
- JSON syntax verified
- All 72 leagues accounted for (20 true, 52 false)

### Next Steps
- Verify pipeline runs with reduced league set
- Monitor hit rate improvement from focused coverage
- Consider further quarantine of Eredivisie/Scottish Premiership per audit findings

---

## 2026-08-25 — Session Work: Cups Restored to Deploy-Eligible

### Implementation Completed
- **File modified**: `config/leagues.json`
- **Change**: Re-enabled 9 domestic cups + UEFA Super Cup as deploy-eligible (per user directive)
- **Cups now TRUE (9):**
  1. Coppa Italia (Italy)
  2. Copa del Rey (Spain)
  3. DFB-Pokal (Germany)
  4. Coupe de France (France)
  5. FA Cup (England)
  6. KNVB Beker (Netherlands)
  7. Taça de Portugal (Portugal)
  8. UEFA Super Cup (World)
  9. EFL Cup (England)

### New Deploy-Eligible Count
- **Total: 29** (20 original top-tier leagues + 9 cups)
- **Deploy-eligible FALSE: 43** (all other minor leagues + Liechtensteiner Cup)

### Rationale
- User explicitly requested cups be restored to eligible list
- Major domestic cups have strong odds coverage via Odds API and API-Football
- EFL Cup specifically was skipped today (2026-08-25) — now back in rotation

### Testing
- JSON syntax verified
- All 72 leagues accounted for (29 true, 43 false)

---

## 2026-08-26 — Session Work: Telegram Push Suppression for Empty Boards

### Implementation Completed
- **File modified**: `run_daily.py`
- **Change**: Added guard at `run_daily.py:1677-1704` to suppress Telegram phone push when the board has no deployable call (no Acca A, no split accas, no singles). The board is still written to `telegram_<date>.txt` for the web feed / audit trail.

### Rationale
- Empty/paper-only boards ("NO DEPLOY-ELIGIBLE CALL this session") are honest, valid outputs — they just don't need to wake the phone.
- Prior behavior: every run that completed `send=True` pushed to Telegram, flooding the channel with zero-call noise.
- New behavior: `has_deployable` checks `production.acca_a`, `production.split_accas`, `production.singles` — only pushes when there's a real deployable call.
- Board still persists to disk + web feed; only the phone push is gated.

### Testing
- Syntax verified (`python -m py_compile run_daily.py`)
- Logic aligns with `build_production_bets` return shape in `engine/acca.py` (production object has `acca_a`, `split_accas`, `singles` attributes).

---

## 2026-08-30 — Session Work: Nightly Production Schedule Shift (22:00 Night Before)

### Implementation Completed
- **Files modified**:
  1. `setup_daily_board_task.ps1` — Windows Task Scheduler trigger changed from `07:00` to `22:00`
  2. `scripts/install_scheduler_tasks.ps1` — Task definition updated to `Daily 22:00`
  3. `.github/workflows/daily.yml` — GitHub Actions cron changed from 07:00 to `0 21 * * *` (21:00 UTC = 22:00 Africa/Lagos)
  4. `run_daily.bat` — Launcher updated to calculate tomorrow's date via PowerShell (handles month/year rollover) and pass `--date %tomorrow%` to `run_daily.py`

### Rationale
- **Architect directive 2026-08-30**: "all production must be made the night before the next change 7am to 10pm the night before"
- Change window: 07:00–22:00 the night before deployment
- Tomorrow's production must be made by 22:00 today
- This ensures boards are ready before the 07:00 change window opens

### Technical Details
- **Windows Task Scheduler**: Primary local automation — runs `run_daily.bat` at 22:00 daily
- **GitHub Actions**: CI/CD backup — runs at 21:00 UTC (22:00 Africa/Lagos) daily
- **run_daily.py**: Already supports `--date` parameter for next-day production via `target_date` argument; `board_date = target_date or today` with `scan_window = max(0, (date.fromisoformat(board_date) - date.today()).days)`
- **run_daily.bat**: Now calculates tomorrow's date using PowerShell `Get-Date -Format yyyy-MM-dd -Date (Get-Date).AddDays(1)` — correctly handles month/year rollover (unlike the previous manual date math)

### Testing
- Syntax verified for all modified files
- PowerShell date calculation tested: `powershell -NoProfile -Command "& {Get-Date -Format yyyy-MM-dd -Date (Get-Date).AddDays(1)}"` returns correct tomorrow date
- Task Scheduler update requires re-running `setup_daily_board_task.ps1` as Administrator

### Next Steps
- Re-run `setup_daily_board_task.ps1` as Administrator to register the 22:00 task
- Verify GitHub Actions workflow triggers at 21:00 UTC tonight
- Monitor first nightly run to confirm board is generated for next day

---

*Generated by daily retrospective audit workflow. Append new entries above this line.*