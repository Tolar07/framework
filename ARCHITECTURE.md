# OLP XDV — Current Architecture Summary

**Generated**: 2026-08-07 (updated 2026-08-11 — multi-key Odds API, publish override live, team-map reverse resolver, softness removed, 18-league unified pool)
**Purpose**: Single source of truth for every moving part, credential, scheduled job, and third-party dependency. Drift like "auto/best-free" routing is caught here, not by accident.

---

## 1. Core Components

| Component | Path | Purpose | Language/Deps |
|-----------|------|---------|---------------|
| **Daily Pipeline** | `run_daily.py` | 07:00 run: grade→fixtures→odds→engine→verify→board→log→notify. Product bet (THE CALL, produced bet, TODAY'S PICKS, accas) is TODAY's fixtures only (2026-08-10); 3-day window is the scan reference | Python 3.12, stdlib + `requests` |
| **Brain (SQLite)** | `brain/store.py` | Persistent memory: model fits, predictions, CLV legs mirror, runs | Python 3.12, sqlite3 (stdlib) |
| **CLV Logger** | `clv/clv_logger.py` | Canonical ledger (JSON) — paper legs, entry/close prices, CLV | Python 3.12, stdlib |
| **Engine Suite** | `engine/` | Dixon-Coles, Elo, xG (Understat), Bookmaker (devigged), Consensus | Python 3.12, stdlib + `numpy` (opt) |
| **League eligibility** | `engine/leagues.py` | **ONE unified pool (ID401)** — 18 whitelisted leagues, all scan- AND deploy-eligible. `engine/softness.py` DELETED 2026-08-11 (ID402 removed); no tier logic remains | Python 3.12 |
| **Market gate** | `engine/markets.py` | **ID405 OPEN** — `BLOCKED = {}`, all five 1X2 markets + O/U + BTTS deployable | Python 3.12 |
| **Acca Builder** | `engine/acca.py` | Production intent (2026-08-10): Acca A = top 4–5 highest-confidence fixtures (each leg the fixture's own highest-probability market), remainder → split accas + singles, legs ranked by model probability, a fixture never in two bets, each with its own booking code | Python 3.12 |
| **Orchestrator** | `orchestrator.py` | Scan per league, fit/reuse models, build board | Python 3.12 |
| **SportyBet Booking** | `booking/booking_codes.py` | Playwright booking-code generator — reads `acca_<date>.json`, drives the SPA, captures BOOKING CODES; codes pre-fill the slip, NEVER stake (Phase-2 safe); per-leg BOOKED/MANUAL | Python 3.12 + Playwright |
| **Team-name mapping** | `booking/team_map.py` | OLP XDV ↔ SportyBet names. Forward (`resolve_team`, fuzzy ok) + REVERSE (`resolve_team_to_model`, EXACT + normalized-exact ONLY, no fuzzy — HR35). Reverse table built first-wins from `SPORTYBET_TEAMS` | Python 3.12 |
| **Telegram Poller** | `output/telegram_commands.py` | Long-polling daemon: `/send`, `/produce`, `/verify`, `/stats`, `/board`, `/why` | Python 3.12, stdlib |
| **Web Dashboard** | `webapp/` | Two-tier: `/dashboard` (public, trimmed) + `/admin` (authed, full) | Python 3.12, stdlib HTTP server |

---

## 2. Scheduled Jobs (Windows Task Scheduler)

| Task Name | Schedule | Batch File | Purpose |
|-----------|----------|------------|---------|
| **OLP XDV Daily Board** | 07:00 daily | `run_daily.bat` | Main pipeline run |
| **OLP XDV Health Monitor** | Every 2h + pre-07:00 | `health_monitor.bat` | System health + self-healing + state-change alerts |
| **OLP XDV Dead Man's Switch** | 08:15 daily | `dead_mans_switch.bat` | Distinct alert if 07:00 run didn't complete |

> **Note**: `setup_poller_daemon.ps1` installs the Telegram poller as a Startup-folder shortcut (not Task Scheduler) because `AtLogOn` triggers need admin.

---

## 3. Credentials & Secrets (all in `.env`, gitignored)

| Key | Source | Purpose | Status |
|-----|--------|---------|--------|
| `ODDS_API_KEY` | the-odds-api.com (personal) | Live odds — **MAIN** source | **SET** — 1/500 remaining (monthly reset restores) |
| `ODDS_API_KEY_BACKUP` | the-odds-api.com (free tier) | Live odds — **BACKUP** (optional, resets monthly; each key pays its own 500/mo) | **EMPTY** (documented slot) |
| `THESPORTSDB_KEY` | thesportsdb.com | Fixtures | **SET** (personal key) |
| `TELEGRAM_BOT_TOKEN` | @BotFather | Bot API + poller | **SET** |
| `TELEGRAM_CHAT_ID` | getUpdates | Delivery target | **SET** |
| `API_FOOTBALL_KEY` | api-football.com | Odds fallback for the 5 deploy leagues (100 req/day) | **SET** |
| `ADMIN_USER` / `ADMIN_PASS` | Local | `/admin` Basic auth | **SET** |
| `ARCHITECT_SIGNOFF` | Local | Architect override of the statistical client-publish gate (2026-08-11 — live side-by-side with paper until mean CLV positive; override never silent, stamped in audit log) | **SET = 1** |
| `WHATSAPP_*` | Meta Cloud API | **RETIRED** (commented out) | **DISABLED** |
| `EMAIL_*` | Gmail SMTP | **OPTIONAL** (commented out) | **DISABLED** |

---

## 4. Third-Party Dependencies

| Service | Tier | Quota | Notes |
|---------|------|-------|-------|
| **The Odds API** | Free | 500 req/mo per key | UK + EU regions; multi-key (`ODDS_API_KEY` + `ODDS_API_KEY_BACKUP`); `QUOTA_HARD_FLOOR=5`, `QUOTA_FLOOR=40`; api-football fallback for the 5 deploy leagues when both keys are spent |
| **TheSportsDB** | Free personal key | Rate-limited | `THESPORTSDB_KEY` set |
| **API-Football** | Free | Odds today±1, 100 req/day | Covers 5 deploy leagues; pace-limited (6s between requests) |
| **Understat** | Free | Big-5 + RFPL xG | No key needed; 6h TTL cache |
| **ESPN Scoreboard** | Free | No key | Continental comps + no-TSDB-ID leagues |
| **Telegram Bot API** | Free | Unlimited | Long-polling (30s) |
| **Meta WhatsApp** | Free | Template-gated | **DISABLED** — recurring token expiry |

---

## 5. Git & Commit Conventions

- **Branch**: `main` (OLP XDV agent at `olp_xdv_agent/olp_xdv`)
- **User**: `tolar07` (repo default)
- **Message suffix**: `Co-Authored-By: Claude <noreply@anthropic.com>`
- **Artifacts committed**: Only meaningful ones (boards when published, RATIFICATIONS.md, code changes); logs/ledger/cache left dirty
- **Safe-move protocol**: Every session MUST `git status --short` + `git log --oneline -5` before work, combine other session's changes, commit ONLY the intended paths (`git commit --only <paths>` so a plain commit never sweeps the other session's staged files)

---

## 6. Critical Gates (Code-Level Hard Fails)

| Gate | Location | Condition | Error Type |
|------|----------|-----------|------------|
| **Capital** | `config.assert_paper_only()` | `PHASE < 3` | `CapitalGateError` |
| **Client Publish** | `webapp/schema.check_client_publish_gate()` | `<30 CLV legs` OR `mean CLV ≤ 0` OR `ARCHITECT_SIGNOFF≠1` — OR override `ARCHITECT_SIGNOFF=1` passes (override stamped honestly in `publish_audit.jsonl` with live gate numbers) | `ClientPublishGateError` |
| **Model Reuse** | `brain/store.content_hash()` | Identical training rows + config | Refuses if hash differs |
| **Schema Refusal** | `brain/store._migrate()` + `schema.read_payload()` | DB/schema newer than code | `RuntimeError` / `ValueError` |
| **HR35 (No Fabrication)** | Throughout | Missing data → `NO DATA — PENDING`; reverse team-map never guesses across clubs | Never guesses |

---

## 7. Data Flow (07:00 Run)

```
run_daily.bat
  └─ run_daily.py
       ├─ load_dotenv() → .env into os.environ (config.py stdlib loader)
       ├─ Brain() + sync_legs() + sync_corrections()
       ├─ grade_open_legs() ← football-data.co.uk CSVs (6h TTL live, 30d completed)
       ├─ scan_one_league() × 18 leagues (ONE unified pool — ID401)
       │    ├─ TheSportsDB fixtures (season feed → eventsday fallback)
       │    ├─ ESPN scoreboard (key-free redundancy)
       │    ├─ SportyBet cache (booking/team_map reverse resolver — exact, no fuzzy)
       │    └─ API-Football (paid fallback)
       ├─ fetch_odds() — _resolve_key walks ODDS_API_KEY then ODDS_API_KEY_BACKUP
       │    (whichever has quota above the floor); if BOTH spent → api-football
       │    fallback for the 5 deploy leagues; otherwise honest NO DATA — PENDING
       │    (HR35, refuses to spend the month)
       ├─ Engine: DC + Elo + xG + Bookmaker (devigged 1X2) → Consensus
       ├─ Market-anchored probability blend (ID414)
       ├─ CLV-gated recalibration (inert until MIN_LEGS=15)
       ├─ log_paper_legs() → clv/clv_log.json (Phase 2 gate)
       ├─ capture_closing_lines() (CL-LIVE, reuses odds_index)
       ├─ produce_bet / THE CALL (today only) + accas (production intent) + booking codes
       ├─ render_telegram_board() + render_produce_bet()
       ├─ write board_<date>.txt + board_<date>.json
       ├─ notify.deliver() → Telegram (fails run if incomplete)
       ├─ whatsapp_deliver.deliver() (copy channel, disabled)
       ├─ email_deliver.deliver() (copy channel, never fails run)
       └─ Brain.update_run(status="ok")
```

---

## 8. Web Dashboard Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  webapp/server.py (ThreadingHTTPServer, 0.0.0.0:8088)      │
├─────────────────────────────────────────────────────────────┤
│  /dashboard/{date}     → schema.read_published()            │
│  /api/board.json       → schema.read_published()            │
│  /history              → public, no internals               │
├─────────────────────────────────────────────────────────────┤
│  /admin/{date}         → schema.read_payload() + Basic Auth │
│  /stats, /why          → Brain, auth required               │
│  /api/admin/board.json → full payload, auth required        │
│  POST /api/admin/publish → schema.write_published()         │
│                          → check_client_publish_gate()      │
│                          (Architect override honored +       │
│                           stamped into audit log)           │
│                          → trim_payload() + audit log       │
└─────────────────────────────────────────────────────────────┘
```

**Data-leak boundary**: `trim_payload()` strips ALL model internals (Elo, xG, consensus, verification, EV, gate, flags, prices) — client only receives market probabilities + picks. The honest-edge statement (mean CLV negative, override active) stays on the client view.

---

## 9. Known Issues / Drift Points (as of 2026-08-11)

| Issue | Severity | Location | Mitigation |
|-------|----------|----------|------------|
| **Odds quota spent (1/500)** | High | `.env` `ODDS_API_KEY` | Multi-key support + api-football fallback in place; monthly reset or a backup key restores full price pulls |
| **Phase 3 gate not met (CLV negative)** | High | `clv/phase3_gate.py` | 12/30 legs with CLV, mean −1.631%; Architect override active for client publish; gate re-blocks if signoff unset |
| **Stale odds-fixture caches** | Medium | `data/cache/fixtures_from_odds/` | Deliberately NOT auto-healed (re-pull spends quota); refreshes on next run once quota returns |
| **Away-market overconfidence** | Structural | engine | Model claims ~39% away, delivers ~30%; needs model refit |
| **Promoted clubs unrated** | Medium | `engine/leagues.py` | Newly promoted clubs need top-flight matches to self-rate — honest `NO DATA — PENDING` until then |

---

## 10. Files Changed This Session (2026-08-11)

| File | Purpose |
|------|---------|
| `pipeline/odds.py` | Multi-key Odds API: `_odds_keys()`, `_probe_key()`, `_resolve_key()` walk `ODDS_API_KEY` → `ODDS_API_KEY_BACKUP`; api-football fallback when both spent; honest `QuotaExhausted` (HR35) |
| `.env` | `ODDS_API_KEY_BACKUP` documented slot; `ARCHITECT_SIGNOFF=1` with rationale |
| `booking/team_map.py` | Verified SportyBet league-page spellings; reverse table `_MODEL_BY_SPORTYBET`; `resolve_team_to_model()` (exact only, no fuzzy) |
| `booking/sportybet_fixtures.py` | Cache builder now resolves SportyBet names → MODEL keys via `resolve_team_to_model` (was calling the forward resolver backwards) |
| `tests/team_map_reverse_test.py` | **NEW** — 33-check regression pinning reverse + no-fuzzy (HR35) |
| `webapp/schema.py` | (existing) `check_client_publish_gate()` honors `ARCHITECT_SIGNOFF=1`; `write_published()` stamps override + live gate numbers into audit log |
| `output/boards/published/board_2026-08-11.json` | Published client board (18 leagues, 13 fixtures, 4 rated) |
| `output/boards/published/publish_audit.jsonl` | Audit entry #3: override + gate numbers stamped |

---

## 11. Verification Commands

```bash
# Safe-move check (every session start)
git status --short
git log --oneline -5

# Run all critical tests
PYTHONIOENCODING=utf-8 py -3.12 tests/team_map_reverse_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/booking_codes_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/webapp_schema_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/dead_mans_switch_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/run_watchdog_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/multi_source_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/brain_store_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/consensus_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/bookmaker_engine_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/recalibration_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/closing_capture_test.py

# Health monitor (exit 0 = all fine, exit 2 = issues exist — BY DESIGN)
PYTHONIOENCODING=utf-8 py -3.12 monitor/health_monitor.py --no-alert

# Check .env is gitignored and no secrets in history
git ls-files | grep -i env          # should show only .env.example
git log --all --full-history -- .env  # should show NO commits

# Verify Task Scheduler tasks exist
schtasks /query /tn "OLP XDV Daily Board"
schtasks /query /tn "OLP XDV Health Monitor"
schtasks /query /tn "OLP XDV Daily Run Dead Man's Switch"
```

---

## 12. Historical CLV Backtest — CURRENT RESULTS (verified 2026-08-08)

**The backtest is NOT blocked.** `backtest/clv_backtest.py` runs the framework's
own engine walk-forward over completed seasons (needs historical closing odds
only — Football-Data.co.uk provides them). It is a DIFFERENT instrument from the
live Phase 2 calibration loop (which genuinely needs 30+ real logged legs).

Recent verified runs (fresh executions, 2026-08-08):

| Run | Fit → Test | Legs | Mean CLV | Beat | t |
|-----|-----------|------|----------|------|---|
| model, 6-league | 2324 → 2425 | 2,776 | **−0.425%** | 46.5% | −2.776 |
| Scottish Premiership only | 2324 → 2425 | 303 | **−0.748%** | 44.5% | −1.479 |
| Scottish Premiership only | 2425 → 2526 | 253 | **+0.626%** | 52.6% | +1.278 |

**Honest reading**: the framework does NOT yet demonstrate a profitable edge.
Cross-season results are mixed (2425 negative, 2526 slightly positive); margin
shrinks toward the close (drift ≈ −0.3pp); the 1X2_A market is consistently
negative. *"A backtest measures; only logged forward CLV proves."*

Re-run command:
```bash
PYTHONIOENCODING=utf-8 py -3.12 backtest/clv_backtest.py --test-season 2526 --carry-in 2425 --leagues "Scottish Premiership"
```

---

## 13. Next Priority Actions (Architect Order)

1. **Restore odds quota** — paste a fresh key in `ODDS_API_KEY`/`ODDS_API_KEY_BACKUP` or wait for the monthly reset; the live blocker
2. **Watch forward CLV daily** — the published board runs live side-by-side with paper until mean CLV turns positive; publish override stays only as long as the Architect keeps `ARCHITECT_SIGNOFF=1`
3. **Model refit for away overconfidence** — structural, needs refit before Phase 3 capital
4. **Keep the team-map reverse resolver honest** — new SportyBet clubs appear each transfer window; add exact spellings to `SPORTYBET_TEAMS` rather than ever weakening the no-fuzzy rule

---

**This document is the single source of truth for architecture. Update it when:**
- A new scheduled job is added/removed
- A credential is added/rotated
- A third-party dependency changes tier/quota
- A hard gate is added/modified
- The safe-move protocol is updated

**Do not rely on memory or chat history — this doc IS the sync mechanism.**
