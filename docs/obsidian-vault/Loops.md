# Loops — Recurring Pipeline Schedules

> Canonical registry of all recurring loops in the OLP XDV framework. Each loop has an owner, schedule, purpose, and failure mode. **This is the single source of truth for Task Scheduler registrations.**

---

## 1. Daily Board (07:00) — `run_daily.py`

| Field | Value |
|-------|-------|
| **Owner** | `run_daily.py` → `olp_xdv_pipeline.py` (10-agent pipeline) |
| **Schedule** | Daily at 07:00 local (Task: "OLP XDV Daily Board") |
| **Purpose** | Full production cycle: SCAN → ingest → odds → engine → verify → board → log → notify |
| **Scope** | All whitelisted leagues, all markets, full CLV logging |
| **Duration** | ~2-5 minutes |
| **Failure mode** | Run Watchdog (post-07:00) detects missing board, alerts |
| **Script** | `setup_daily_board_task.ps1` |

**Key behaviour:**
- Generates `output/boards/board_YYYY-MM-DD.json`
- Delivers to Telegram (and WhatsApp/email if configured)
- Logs to `logs/daily_YYYY-MM-DD.log`
- Updates brain runs table with full telemetry

---

## 2. Hourly Fixture Check (Every Hour) — `scripts/hourly-fixture-check.js`

| Field | Value |
|-------|-------|
| **Owner** | `scripts/hourly-fixture-check.js` |
| **Schedule** | Every hour, starting at top of next hour (Task: "OLP XDV Hourly Fixture Check") |
| **Purpose** | Refresh awareness of upcoming fixtures; run lightweight pipeline (agents 1-4) if board exists; run full pipeline if no board for today |
| **Scope** | Only fixtures with `match_date >= today` and `hit IS NULL` (not yet kicked off) |
| **Duration** | ~30-60 seconds (lightweight) / ~2-5 min (full if triggered) |
| **Failure mode** | Logs to `logs/hourly-fixture-check/hourly-fixture-YYYY-MM-DD.log`; Dead Man's Switch catches prolonged silence |
| **Script** | `setup_hourly_fixture_check_task.ps1` |

**Key behaviour:**
- Queries `predictions` table for fixtures with `hit IS NULL` and `match_date >= date('now')`
- Filters to matches **not yet kicked off** (by match_date)
- If no board for today → runs full `run_daily.py`
- If board exists → runs lightweight `olp_xdv_pipeline.py --only 1-4 --dry-run`
- Skips matches that have already kicked off (no point generating bets on live games)
- Maintains state in `data/hourly-fixture-state.json`

**Why hourly?**
- Daily 07:00 run misses fixtures added after 07:00
- Matches kick off throughout the day — framework should adapt
- "Focus on the one that is yet to start" — don't waste cycles on live/finished matches
- Enables continuous odds refresh and fixture discovery

---

## 3. Health Monitor (Every 2 Hours) — `monitor/health_monitor.py`

| Field | Value |
|-------|-------|
| **Owner** | `monitor/health_monitor.py` |
| **Schedule** | Every 2 hours (Task: "OLP XDV Health Monitor") |
| **Purpose** | System health probes: DB connectivity, API keys, disk space, process liveness |
| **Duration** | ~10-30 seconds |
| **Failure mode** | Alerts via Telegram on CRITICAL; logs to `logs/health-monitor/` |

---

## 4. Run Watchdog (Post-07:00) — `monitor/run_watchdog.py`

| Field | Value |
|-------|-------|
| **Owner** | `monitor/run_watchdog.py` |
| **Schedule** | 07:15, 07:30, 08:00, 09:00 (Task: "OLP XDV Run Watchdog") |
| **Purpose** | Detect missing daily board after 07:00 run window |
| **Duration** | ~5 seconds |
| **Failure mode** | Telegram alert if board missing by 09:00 |

---

## 5. Data Steward (06:00 + 15:00) — `steward/run_steward.py`

| Field | Value |
|-------|-------|
| **Owner** | `steward/run_steward.py` |
| **Schedule** | 06:00 and 15:00 daily (Task: "OLP XDV Data Steward") |
| **Purpose** | Cache warming, fixture pre-fetch, historical backfill, team map audit |
| **Duration** | ~1-3 minutes |
| **Failure mode** | Logs to `logs/steward/`; non-blocking |

---

## 6. Dead Man's Switch (Nightly) — `monitor/dead_mans_switch.py`

| Field | Value |
|-------|-------|
| **Owner** | `monitor/dead_mans_switch.py` |
| **Schedule** | 02:00 daily (Task: "OLP XDV Dead Man's Switch") |
| **Purpose** | Verify framework is alive — checks recent logs, DB writes, Telegram connectivity |
| **Duration** | ~10 seconds |
| **Failure mode** | Telegram alert if no activity > 26 hours |

---

## 7. Hourly Match Analysis (Every Hour) — `scripts/hourly-match-analysis.js`

| Field | Value |
|-------|-------|
| **Owner** | `scripts/hourly-match-analysis.js` |
| **Schedule** | Every hour (Task: "OLP XDV Hourly Match Analysis") |
| **Purpose** | Continuous learning from settled matches: CLV, calibration, miss patterns, weight updates |
| **Scope** | Settled predictions (`hit IS NOT NULL`) since last run |
| **Duration** | ~10-30 seconds |
| **Failure mode** | Logs to `logs/hourly-analysis/`; non-blocking |

---

## Task Scheduler Registration Scripts

All Task Scheduler registrations use elevated PowerShell scripts in the repo root:

| Script | Task Name | Run Level |
|--------|-----------|-----------|
| `setup_daily_board_task.ps1` | "OLP XDV Daily Board" | Highest |
| `setup_hourly_fixture_check_task.ps1` | "OLP XDV Hourly Fixture Check" | Highest |
| `setup_health_monitor_task.ps1` | "OLP XDV Health Monitor" | Highest |
| `setup_dead_mans_switch_task.ps1` | "OLP XDV Dead Man's Switch" | Highest |

**Registration command (run from ADMIN PowerShell):**
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File setup_daily_board_task.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File setup_hourly_fixture_check_task.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File setup_health_monitor_task.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File setup_dead_mans_switch_task.ps1
```

---

## Architecture Notes

### The "Supervisor" Concept
The user refers to a "supervisor/owner agent" — in OLP XDV this is **not a single agent** but the **ensemble of scheduled tasks** above. The hourly fixture check (Loop 2) is the new loop that addresses the user's request:
> "check for fixtures/matches every hour instead of once daily at 07:00... focus on the one that is yet to start"

### Interaction Between Loops
- **Daily Board (07:00)** → Full production run, creates the day's board
- **Hourly Fixture Check** → If board missing, triggers full run; if board exists, lightweight refresh
- **Hourly Match Analysis** → Learns from settled matches, updates weights for next cycle
- **Health Monitor** → Ensures infrastructure is healthy
- **Data Steward** → Warms caches before daily run

### State Persistence
Each loop maintains its own state file:
- Hourly Fixture Check → `data/hourly-fixture-state.json`
- Hourly Match Analysis → `data/learning/last-analysis-state.json`
- Data Steward → `data/steward-state.json`

---

## Adding a New Loop

1. Create the script in `scripts/` or `monitor/`
2. Add entry to this file (Loops.md)
3. Create `setup_<loop>_task.ps1` following the pattern
4. Register via ADMIN PowerShell
5. Verify in Task Scheduler and check first run logs

---

*Last updated: 2026-08-21 — Added Hourly Fixture Check loop per Architect directive*