# OLP XDV — Current Architecture Summary

**Generated**: 2026-08-07  
**Purpose**: Single source of truth for every moving part, credential, scheduled job, and third-party dependency. Drift like "auto/best-free" routing is caught here, not by accident.

---

## 1. Core Components

| Component | Path | Purpose | Language/Deps |
|-----------|------|---------|---------------|
| **Daily Pipeline** | `run_daily.py` | 07:00 run: grade→fixtures→odds→engine→verify→board→log→notify | Python 3.12, stdlib + `requests` |
| **Brain (SQLite)** | `brain/store.py` | Persistent memory: model fits, predictions, CLV legs mirror, runs | Python 3.12, sqlite3 (stdlib) |
| **CLV Logger** | `clv/clv_logger.py` | Canonical ledger (JSON) — paper legs, entry/close prices, CLV | Python 3.12, stdlib |
| **Engine Suite** | `engine/` | Dixon-Coles, Elo, xG (Understat), Bookmaker (devigged), Consensus | Python 3.12, stdlib + `numpy` (opt) |
| **Orchestrator** | `orchestrator.py` | Scan per league, fit/reuse models, build board | Python 3.12 |
| **Telegram Poller** | `output/telegram_commands.py` | Long-polling daemon: `/send`, `/produce`, `/verify`, `/stats`, `/board`, `/why` | Python 3.12, stdlib |
| **Web Dashboard** | `webapp/` | Two-tier: `/dashboard` (public, trimmed) + `/admin` (authed, full) | Python 3.12, stdlib HTTP server |

---

## 2. Scheduled Jobs (Windows Task Scheduler)

| Task Name | Schedule | Batch File | Purpose |
|-----------|----------|------------|---------|
| **OLP XDV Daily Board** | 07:00 daily | `run_daily.bat` | Main pipeline run |
| **OLP XDV Health Monitor** | Every 2h + pre-07:00 | `health_monitor.bat` | System health + self-healing + state-change alerts |
| **OLP XDV Dead Man's Switch** | 08:15 daily | `dead_mans_switch.bat` | **NEW** — distinct alert if 07:00 run didn't complete |

> **Note**: `setup_poller_daemon.ps1` installs the Telegram poller as a Startup-folder shortcut (not Task Scheduler) because `AtLogOn` triggers need admin.

---

## 3. Credentials & Secrets (all in `.env`, gitignored)

| Key | Source | Purpose | Status |
|-----|--------|---------|--------|
| `ODDS_API_KEY` | the-odds-api.com | Live odds for MES entry prices | **SET** |
| `THESPORTSDB_KEY` | thesportsdb.com | Fixtures (fallback: shared key "123") | **EMPTY** — rate-limited |
| `TELEGRAM_BOT_TOKEN` | @BotFather | Bot API + poller | **SET** |
| `TELEGRAM_CHAT_ID` | getUpdates | Delivery target | **SET** |
| `API_FOOTBALL_KEY` | api-football.com | Historical results fallback (paid only) | **SET** (free tier — limited) |
| `ADMIN_USER` / `ADMIN_PASS` | Local | `/admin` Basic auth | **SET** |
| `ARCHITECT_SIGNOFF` | Local | Hard gate for client publish | **NOT SET** (defaults to required) |
| `WHATSAPP_*` | Meta Cloud API | **RETIRED** (commented out) | **DISABLED** |
| `EMAIL_*` | Gmail SMTP | **OPTIONAL** (commented out) | **DISABLED** |

---

## 4. Third-Party Dependencies

| Service | Tier | Quota | Notes |
|---------|------|-------|-------|
| **The Odds API** | Free | 500 req/mo | UK + EU regions; `QUOTA_HARD_FLOOR=5`, `QUOTA_FLOOR=40` |
| **TheSportsDB** | Free test key | Rate-limited | `THESPORTSDB_KEY` empty → uses shared "123" |
| **API-Football** | Free | History only (≤2024) | Current season blocked — paid plan needed |
| **Understat** | Free | Big-5 + RFPL xG | No key needed; 6h TTL cache |
| **ESPN Scoreboard** | Free | No key | Continental comps + no-TSDB-ID leagues |
| **Telegram Bot API** | Free | Unlimited | Long-polling (30s) |
| **Meta WhatsApp** | Free | Template-gated | **DISABLED** — recurring token expiry |

---

## 5. Git & Commit Conventions

- **Branch**: `elo-persistence`
- **User**: `git -c user.name=olp-xdv -c user.email=olp-xdv@local`
- **Message suffix**: `Co-Authored-By: Claude <noreply@anthropic.com>`
- **Artifacts committed**: Only meaningful ones (boards when published, RATIFICATIONS.md); logs/ledger/cache left dirty
- **Safe-move protocol**: Every session MUST `git status --short` + `git log --oneline -5` before work, combine other session's changes, commit combined state

---

## 6. Critical Gates (Code-Level Hard Fails)

| Gate | Location | Condition | Error Type |
|------|----------|-----------|------------|
| **Capital** | `config.assert_paper_only()` | `PHASE < 3` | `CapitalGateError` |
| **Client Publish** | `webapp/schema.check_client_publish_gate()` | `<30 CLV legs` OR `mean CLV ≤ 0` OR `ARCHITECT_SIGNOFF≠1` | `ClientPublishGateError` |
| **Model Reuse** | `brain/store.content_hash()` | Identical training rows + config | Refuses if hash differs |
| **Schema Refusal** | `brain/store._migrate()` + `schema.read_payload()` | DB/schema newer than code | `RuntimeError` / `ValueError` |
| **HR35 (No Fabrication)** | Throughout | Missing data → `NO DATA — PENDING` | Never guesses |

---

## 7. Data Flow (07:00 Run)

```
run_daily.bat
  └─ run_daily.py
       ├─ load_dotenv() → .env into os.environ
       ├─ Brain() + sync_legs() + sync_corrections()
       ├─ grade_open_legs() ← football-data.co.uk CSVs (6h TTL live, 30d completed)
       ├─ scan_one_league() × 16 leagues
       │    ├─ TheSportsDB fixtures (season feed → eventsday fallback)
       │    ├─ ESPN scoreboard (NEW: key-free redundancy)
       │    ├─ Odds-derived fixtures (last resort)
       │    └─ API-Football (paid fallback)
       ├─ fetch_odds() for deploy-eligible leagues only (quota protection)
       ├─ Engine: DC + Elo + xG + Bookmaker (devigged 1X2) → Consensus
       ├─ Market-anchored probability blend (ID414)
       ├─ CLV-gated recalibration (inert until MIN_LEGS=15)
       ├─ log_paper_legs() → clv/clv_log.json (Phase 2 gate)
       ├─ capture_closing_lines() (CL-LIVE, reuses odds_index)
       ├─ render_telegram_board() + render_produce_bet()
       ├─ write board_<date>.txt + board_<date>.json
       ├─ notify.deliver() → Telegram (fails run if incomplete)
       ├─ whatsapp_deliver.deliver() (copy channel, never fails run)
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
│                          → trim_payload() + audit log       │
└─────────────────────────────────────────────────────────────┘
```

**Data-leak boundary**: `trim_payload()` strips ALL model internals (Elo, xG, consensus, verification, EV, gate, flags, prices) — client only receives market probabilities + picks.

---

## 9. Known Issues / Drift Points (as of 2026-08-07)

| Issue | Severity | Location | Mitigation |
|-------|----------|----------|------------|
| **THESPORTSDB_KEY empty** | High | `.env` | Register personal key at thesportsdb.com |
| **Odds quota low (4/500)** | High | `pipeline/odds.py` | Monthly reset; monitor via health monitor |
| **Telegram delivery failing** | Critical | `logs/daily_*.log` | Check bot token / poller daemon |
| **Stale fixture caches (18-25h)** | Medium | `data/cache/` | Self-heals on next run (6h TTL rejection) |
| **Promoted clubs unrated** | Medium | `engine/softness.py` | 5 clubs need top-flight matches to self-rate |
| **No backtest run against real history** | Critical | `backtest/` | Blocked by missing historical prediction log |
| **ARCHITECT_SIGNOFF not set** | Medium | `.env` | Required for client publish gate |

---

## 10. Files Created This Session (Structural Fixes)

| File | Purpose |
|------|---------|
| `webapp/schema.py` | Added `ClientPublishGateError` + `check_client_publish_gate()` — hard blocks publish until Phase 3 gate met |
| `monitor/dead_mans_switch.py` | Dead-man's-switch: distinct 08:00 alert if 07:00 run incomplete |
| `dead_mans_switch.bat` | Batch launcher for dead-man's-switch |
| `setup_dead_mans_switch_task.ps1` | Task Scheduler registration for dead-man's-switch |
| `tests/dead_mans_switch_test.py` | Test suite (8 tests passing) |
| `tests/webapp_schema_test.py` | Extended with gate tests (8 new tests passing) |

---

## 11. Verification Commands

```bash
# Safe-move check (every session start)
git status --short
git log --oneline -5

# Run all critical tests
PYTHONIOENCODING=utf-8 py -3.12 tests/webapp_schema_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/dead_mans_switch_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/run_watchdog_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/multi_source_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/brain_store_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/consensus_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/bookmaker_engine_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/recalibration_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/softness_mes_test.py
PYTHONIOENCODING=utf-8 py -3.12 tests/closing_capture_test.py

# Check .env is gitignored and no secrets in history
git ls-files | grep -i env          # should show only .env.example
git log --all --full-history -- .env  # should show NO commits

# Verify Task Scheduler tasks exist
schtasks /query /tn "OLP XDV Daily Board"
schtasks /query /tn "OLP XDV Health Monitor"
schtasks /query /tn "OLP XDV Daily Run Dead Man's Switch"
```

---

## 12. Next Priority Actions (Architect Order)

1. **Run backtest against real historical data** — unblocks "demonstrated edge" question
2. **Set THESPORTSDB_KEY** — eliminates rate-limiting on fixtures
3. **Debug Telegram delivery failure** — check poller daemon + bot token
4. **Monitor quota reset** — daily run needs odds to log legs
5. **Set ARCHITECT_SIGNOFF=1** — only AFTER reviewing a board that meets Phase 3 gate

---

**This document is the single source of truth for architecture. Update it when:**
- A new scheduled job is added/removed
- A credential is added/rotated
- A third-party dependency changes tier/quota
- A hard gate is added/modified
- The safe-move protocol is updated

**Do not rely on memory or chat history — this doc IS the sync mechanism.**