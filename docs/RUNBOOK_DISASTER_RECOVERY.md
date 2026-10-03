# Disaster Recovery Runbook — OLP XDV

**Last updated:** 2026-08-13
**Owner:** Architect (capital authority), Steward (ops)
**Scope:** How to get OLP XDV publishing the daily board again after the machine dies, is wiped, or the service silently stops.

---

## 1. Irreplaceable State (the only thing that matters in a DR)

| State | Location | Git-tracked? | Rebuildable? | Recovery Priority |
|-------|----------|--------------|--------------|-------------------|
| **Secrets (API keys, Telegram tokens, encryption key)** | `.env` | ❌ gitignored | ❌ **NO** | **P0 — without this, nothing works** |
| CLV ledger (canonical) | `clv/clv_log.json` | ✅ tracked | N/A (is the source) | P0 |
| Brain DB | `brain/olp.db` | ❌ gitignored | ⚠ from clv_log.json + model history | P1 |
| Health monitor alert state | `logs/health_state.json` | ❌ gitignored | ⚠ partial (re-alerts after 26h) | P1 |
| Published boards | `output/boards/published/*.json` | ❌ gitignored | ⚠ from brain + engine re-run | P2 |
| Steward state | `logs/steward_state.json` | ❌ gitignored | ⚠ re-fetch next run | P2 |
| Caddy certs (Let's Encrypt) | `data/caddy/` | ❌ gitignored | ⚠ re-issue on domain | P2 |
| Logs (audit trail) | `logs/*.log` | ❌ gitignored | ❌ NO (but not runtime-critical) | P3 |

**The single most important file is `.env`** — it holds every API key, the Telegram bot token, and `BACKUP_ENC_KEY`. Without it, you cannot pull live odds, send Telegram, or decrypt the backup.

---

## 2. Prerequisites (on the rescue machine)

You need a Windows machine (the deployment target is Windows + Task Scheduler + NSSM). Install:

| Tool | Install | Verify |
|------|---------|--------|
| **Python 3.12** | https://www.python.org/downloads/ (or `winget install Python.Python.3.12`) | `python --version` → 3.12.x |
| **Git** | https://git-scm.com/ | `git --version` |
| **Caddy** | `scoop install caddy` OR `choco install caddy` | `caddy version` |
| **NSSM** | `scoop install nssm` OR `choco install nssm` | `nssm version` |
| **rclone** | https://rclone.org/downloads/ (or `winget install Rclone.Rclone`) | `rclone version` |
| **OpenSSL** | Ships with Git for Windows (`C:\Program Files\Git\usr\bin\openssl.exe`) or `winget install OpenSSL` | `openssl version` |

---

## 3. Restore from backup

### 3.1 Get the latest backup

```powershell
# From rclone remote (preferred)
rclone copy <BACKUP_RCLONE_REMOTE>/olp-backup-<latest>.zip C:\olp-restore\

# Or use local backups/ if you have a recent copy
Copy-Item "C:\path\to\backups\olp-backup-<latest>.zip" C:\olp-restore\
```

### 3.2 Decrypt `.env`

```powershell
cd C:\olp-restore
# Decrypt .env.enc → .env (uses BACKUP_ENC_KEY from the rescue machine's .env or manual entry)
$encKey = Read-Host -AsSecureString "Enter BACKUP_ENC_KEY"
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($encKey)
$key = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# Find openssl
$openssl = "C:\Program Files\Git\usr\bin\openssl.exe"
if (-not (Test-Path $openssl)) { $openssl = "openssl" }

& $openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 -k $key -in .env.enc -out .env
```

Verify the decrypted `.env` has all required keys:
```powershell
Get-Content .env | Select-String "^(TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID|ODDS_API_KEY|ANTHROPIC_API_KEY|FOOTBALL_DATA_API_KEY|BACKUP_ENC_KEY)="
```

---

## 4. Deploy the application

### 4.1 Clone + place files

```powershell
git clone <repo-url> "C:\Users\Motunrayo\omniroute test\olp_xdv_agent"
cd "C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv"

# Restore machine-only state from the unzipped backup
Copy-Item "C:\olp-restore\.env" .env
Copy-Item "C:\olp-restore\clv_log.json" clv\
Copy-Item "C:\olp-restore\olp.db" brain\
Copy-Item "C:\olp-restore\health_state.json" logs\
Copy-Item "C:\olp-restore\steward_state.json" logs\
Copy-Item "C:\olp-restore\published\*" output\boards\published\ -Recurse -Force
Copy-Item "C:\olp-restore\caddy_data" data\caddy -Recurse -Force
```

### 4.2 Install Python deps (if any)

```powershell
pip install -r requirements.txt   # if present
# or
py -m pip install -r requirements.txt
```

### 4.3 Install the web tier as a service (NSSM)

```powershell
# Admin PowerShell
powershell -ExecutionPolicy Bypass -File scripts\install_web_service.ps1
```

Verify:
```powershell
Get-Service "OLP XDV Web" | Select-Object Status, StartType
# Status should be Running, StartType Automatic
```

### 4.4 Harden all scheduled tasks (reboot-survival + restart-on-failure)

```powershell
# Admin PowerShell
powershell -ExecutionPolicy Bypass -File scripts\install_scheduler_tasks.ps1
```

Verify:
```powershell
Get-ScheduledTask | Where-Object { $_.TaskName -like 'OLP XDV*' } |
    Select-Object TaskName, State, @{N='RestartCount';E={$_.Settings.RestartCount}}
```

### 4.5 Install the Telegram poller daemon (Startup shortcut)

```powershell
powershell -ExecutionPolicy Bypass -File setup_poller_daemon.ps1
```

---

## 5. Verify the deployment

### 5.1 Web health check

```powershell
# Local
curl https://localhost/health        # behind Caddy (TLS)
curl http://127.0.0.1:8088/health    # direct Python

# Should return: {"status": "ok", "service": "olp-xdv-dashboard", "version": "2.0.0"}
```

### 5.2 Metrics endpoint

```powershell
curl https://localhost/metrics
# Should return Prometheus-format text
```

### 5.3 Error tracking endpoint

```powershell
curl https://localhost/api/errors/summary
# Should return {"total_errors": ..., "unique_error_ids": ..., "by_error_id": {...}}
```

### 5.4 Trigger a manual daily run

```powershell
cd "C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv"
python run_daily.py --no-send    # dry-run without delivery
# then, if clean:
python run_daily.py              # full run + Telegram delivery
```

### 5.5 Verify Telegram delivery

Check your Telegram — the board should arrive. If not:
- Check `logs\launcher.log` and `logs\daily_<today>.log` for errors
- Check `logs\web_server.log` for web tier issues
- Run `python -m monitor.alert_dispatcher critical "Test" "Manual DR test"` to confirm alerts fire

---

## 6. Monitoring after recovery

| Check | How | Alert if |
|-------|-----|----------|
| Daily run completed | `logs\daily_<today>.log` has "run completed OK" + "delivered N part(s) to Telegram" | Dead-man's-switch fires 08:00 |
| Web tier alive | `Get-Service "OLP XDV Web"` = Running | NSSM restarts automatically; if it keeps crashing, check `logs\web_server.log` |
| Health monitor | `logs\health_monitor.log` has a line every 2h | No line in 3h = task died |
| Errors accumulating | `curl /api/errors/summary` shows rising `total_errors` | Wire `ERROR_ALERT_PATTERNS` in `.env` |
| Backup fresh | Latest `backups/olp-backup-*.zip` < 24h old | Backup task failed |

---

## 7. Monthly restore test (CI-gated)

The `scripts\restore_test.ps1` script downloads the latest backup, decrypts `.env`, and verifies:
1. `.env` decrypts + all required keys present
2. `clv/clv_log.json` parses + ≥30 legs with CLV (Phase 3 gate)
3. `brain/olp.db` opens + schema version = 8
4. `python -m olp_xdv.clv.verify` passes
5. `webapp/server.py --health-check` returns 200
6. Published boards present

Run it manually or schedule it (monthly, 1st at 04:00):
```powershell
# Admin PowerShell — register the monthly restore-test task
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$PWD\scripts\restore_test.ps1`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "04:00"
Register-ScheduledTask -TaskName "OLP XDV Restore Test" `
    -Action $action -Trigger $trigger -Force
```

On failure it fires `alert_dispatcher` with tags `["dr", "restore-test-failed"]`.

---

## 8. Emergency contacts & escalation

| Who | When |
|-----|------|
| **Architect** | Any decision touching capital, CLV gate, publish logic, ID405 scope |
| **Steward (ops)** | Routine DR, backup/restore, service restarts |
| **Telegram** | Primary alert channel (fallback: email + webhook if configured) |

**Never** modify protected constants during DR without Architect sign-off:
- `ARCHITECT_SIGNOFF` flag
- CLV publish gate (12/30 legs, mean CLV positive)
- Client-publish gating
- Capital-deployment logic
- Softness-tier defaults (open/cancelled — do not restore Tier A/B)
- ID405 away-win exclusion scope (currently overridden — all markets open)
- Calibration-log league-inclusion scope

---

## 9. Quick reference

```powershell
# Status snapshot
Get-Service "OLP XDV Web" | Select-Object Status, StartType
Get-ScheduledTask | Where-Object { $_.TaskName -like 'OLP XDV*' } | Select-Object TaskName, State
curl https://localhost/health

# Manual operations
Stop-Service "OLP XDV Web"      # NSSM restarts it after 5s
Start-Service "OLP XDV Web"
python run_daily.py --date 2026-08-13   # backfill a missed day

# Backup now
powershell -ExecutionPolicy Bypass -File scripts\backup_daily.ps1 -NoOffsite

# Test restore
powershell -ExecutionPolicy Bypass -File scripts\restore_test.ps1 -UseLocal
```

---

*This runbook is version-controlled. Update it after every DR drill or infrastructure change.*
