<#
.SYNOPSIS
    Monthly restore test — verifies the latest backup can be decrypted and all
    critical state is intact. Fires alert on failure.

.DESCRIPTION
    Downloads the latest backup from rclone remote (or uses local backups/),
    decrypts .env.enc, and runs a battery of verification checks:
      1. .env decrypts + all required keys present
      2. clv/clv_log.json parses + has >= 30 legs with CLV (Phase 3 gate)
      3. brain/olp.db opens + schema version = 8
      4. python -m olp_xdv.clv.verify passes
      5. python webapp/server.py --health-check returns 200 (if server can start)

    On failure: fires alert_dispatcher with tags ["dr", "restore-test-failed"].

.PARAMETER Remote
    rclone remote:path (default: from .env BACKUP_RCLONE_REMOTE).

.PARAMETER LocalDir
    Local backups directory (default: <repo>\backups).

.PARAMETER UseLocal
    Skip rclone download; use latest local backup.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\restore_test.ps1
    powershell -ExecutionPolicy Bypass -File scripts\restore_test.ps1 -UseLocal
#>
param(
    [string]$Remote = "",
    [string]$LocalDir = "",
    [switch]$UseLocal
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

# Read .env for config
$envFile = Join-Path $RepoRoot ".env"
$envVars = @{}
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $k, $v = $line.Split("=", 2)
            $envVars[$k.Trim()] = $v.Trim()
        }
    }
}

$encKey = $envVars["BACKUP_ENC_KEY"]
if (-not $encKey) {
    Write-Error "BACKUP_ENC_KEY not set in .env"
    exit 1
}

if (-not $Remote) {
    $Remote = $envVars["BACKUP_RCLONE_REMOTE"]
}
if (-not $LocalDir) {
    $LocalDir = Join-Path $RepoRoot "backups"
}

# Find latest backup
if ($UseLocal) {
    $latest = Get-ChildItem $LocalDir -Filter "olp-backup-*.zip" |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) {
        Write-Error "No local backup found in $LocalDir"
        exit 1
    }
    $zipPath = $latest.FullName
    $backupName = $latest.BaseName
    Write-Host "Using local backup: $zipPath"
} else {
    if (-not $Remote) {
        Write-Error "No rclone remote configured (BACKUP_RCLONE_REMOTE in .env or -Remote)"
        exit 1
    }
    Write-Host "Listing remote backups at $Remote ..."
    $list = & rclone lsf $Remote --files-only --include "olp-backup-*.zip" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "rclone lsf failed: $list"
        exit 1
    }
    $files = $list.Split([Environment]::NewLine, [StringSplitOptions]::RemoveEmptyEntries) | Sort-Object -Descending
    if (-not $files) {
        Write-Error "No backups found on remote"
        exit 1
    }
    $latestFile = $files[0]
    $backupName = [IO.Path]::GetFileNameWithoutExtension($latestFile)
    $zipPath = Join-Path $LocalDir $latestFile
    Write-Host "Downloading: $latestFile"
    & rclone copy "$Remote/$latestFile" $LocalDir 2>&1 | ForEach-Object { Write-Host "  rclone: $_" }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $zipPath)) {
        Write-Error "rclone copy failed"
        exit 1
    }
}

# Create temp dir for restore
$tempDir = Join-Path $env:TEMP "olp-restore-test-$((Get-Date -Format 'yyyyMMddHHmmss'))"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
Write-Host "Restore test dir: $tempDir"

# Unzip
Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force
$stage = Join-Path $tempDir "stage"
if (-not (Test-Path $stage)) {
    # Maybe flat zip
    $stage = $tempDir
}

Write-Host "`n=== VERIFICATION CHECKS ==="

$allPassed = $true
$notes = @()

# 1. Decrypt .env.enc → verify required keys
Write-Host "`n[1/6] Decrypting .env.enc ..."
$encFile = Join-Path $stage ".env.enc"
$decryptedEnv = Join-Path $tempDir ".env.decrypted"
if (Test-Path $encFile) {
    & openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 `
        -k $encKey -in $encFile -out $decryptedEnv 2>$null
    if ($LASTEXITCODE -eq 0 -and (Test-Path $decryptedEnv)) {
        Write-Host "  OK: .env decrypted"
        $keys = @(
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
            "ODDS_API_KEY", "ANTHROPIC_API_KEY",
            "FOOTBALL_DATA_API_KEY"
        )
        $missing = @()
        $content = Get-Content $decryptedEnv -Raw
        foreach ($k in $keys) {
            if ($content -notmatch "^$k\s*=") {
                $missing += $k
            }
        }
        if ($missing) {
            Write-Warning "  MISSING keys: $($missing -join ', ')"
            $allPassed = $false
            $notes += "ENV_MISSING_KEYS: $($missing -join ',')"
        } else {
            Write-Host "  OK: All required keys present"
            $notes += "ENV_OK"
        }
    } else {
        Write-Error "  FAIL: .env decryption failed"
        $allPassed = $false
        $notes += "ENV_DECRYPT_FAILED"
    }
} else {
    Write-Error "  FAIL: .env.enc not in backup"
    $allPassed = $false
    $notes += "ENV_ENC_MISSING"
}

# 2. clv/clv_log.json parses + >= 30 legs with CLV
Write-Host "`n[2/6] Checking CLV ledger ..."
$clvPath = Join-Path $stage "clv_log.json"
if (Test-Path $clvPath) {
    try {
        $clv = Get-Content $clvPath -Raw | ConvertFrom-Json
        $legs = if ($clv.legs) { $clv.legs.Count } else { 0 }
        $clvLegs = 0
        if ($clv.legs) {
            $clvLegs = ($clv.legs | Where-Object { $_.clv_pct -ne $null }).Count
        }
        Write-Host "  Total legs: $legs, legs with CLV: $clvLegs"
        if ($clvLegs -ge 30) {
            Write-Host "  OK: Phase 3 gate satisfied (>=30 legs with CLV)"
            $notes += "CLV_GATE_OK"
        } else {
            Write-Warning "  BELOW GATE: $clvLegs/30 legs with CLV"
            $notes += "CLV_GATE_LOW:$clvLegs"
            # Not a hard fail — just a warning
        }
    } catch {
        Write-Error "  FAIL: clv_log.json invalid JSON: $_"
        $allPassed = $false
        $notes += "CLV_JSON_INVALID"
    }
} else {
    Write-Error "  FAIL: clv_log.json not in backup"
    $allPassed = $false
    $notes += "CLV_MISSING"
}

# 3. brain/olp.db opens + schema version = 8
Write-Host "`n[3/6] Checking brain DB ..."
$dbPath = Join-Path $stage "olp.db"
if (Test-Path $dbPath) {
    $py = "C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"
    if (-not (Test-Path $py)) { $py = "py" }
    $cmd = "& `"$py`" -c `"import sqlite3; conn=sqlite3.connect(r'$dbPath'); c=conn.cursor(); c.execute('PRAGMA user_version'); v=c.fetchone(); print('schema_version:', v[0] if v else 'none'); conn.close()`""
    $result = Invoke-Expression $cmd 2>&1
    if ($LASTEXITCODE -eq 0 -and $result -match "schema_version:\s*8") {
        Write-Host "  OK: brain DB opens, schema version = 8"
        $notes += "BRAIN_DB_OK"
    } else {
        Write-Error "  FAIL: brain DB check failed: $result"
        $allPassed = $false
        $notes += "BRAIN_DB_FAIL"
    }
} else {
    Write-Warning "  SKIP: olp.db not in backup (rebuildable from clv_log.json)"
    $notes += "BRAIN_DB_SKIPPED"
}

# 4. python -m olp_xdv.clv.verify passes
Write-Host "`n[4/6] Running CLV verification ..."
$py = "C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $py)) { $py = "py" }
# Temporarily point clv_log at the restored one
$cmd = "& `"$py`" -m olp_xdv.clv.verify --ledger `"$clvPath`" 2>&1"
$result = Invoke-Expression $cmd 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK: CLV verification passed"
    $notes += "CLV_VERIFY_OK"
} else {
    Write-Error "  FAIL: CLV verification failed: $result"
    $allPassed = $false
    $notes += "CLV_VERIFY_FAIL"
}

# 5. Test web server health endpoint (start server, hit /health, stop)
Write-Host "`n[5/6] Testing web server health endpoint ..."
$serverExe = Join-Path $RepoRoot "webapp\server.py"
if (Test-Path $serverExe) {
    # Start server in background on a test port
    $testPort = 18088
    $proc = Start-Process -FilePath $py -ArgumentList "-u `"$serverExe`" --host 127.0.0.1 --port $testPort" -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 3
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:$testPort/health" -TimeoutSec 10 -ErrorAction Stop
        if ($resp.status -eq "ok") {
            Write-Host "  OK: /health returns 200"
            $notes += "WEB_HEALTH_OK"
        } else {
            Write-Error "  FAIL: /health returned unexpected: $resp"
            $allPassed = $false
            $notes += "WEB_HEALTH_BAD"
        }
    } catch {
        Write-Error "  FAIL: /health request failed: $_"
        $allPassed = $false
        $notes += "WEB_HEALTH_FAIL"
    } finally {
        if ($proc -and -not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }
} else {
    Write-Warning "  SKIP: webapp/server.py not found"
    $notes += "WEB_SKIPPED"
}

# 6. Check published boards present (last 7 days)
Write-Host "`n[6/6] Checking published boards ..."
$pubStage = Join-Path $stage "published"
if (Test-Path $pubStage) {
    $count = (Get-ChildItem $pubStage -Filter "*.json").Count
    Write-Host "  Published boards in backup: $count"
    $notes += "PUBLISHED_BOARDS:$count"
} else {
    Write-Host "  No published/ dir in backup (optional)"
    $notes += "PUBLISHED_MISSING"
}

# Summary
Write-Host "`n=== RESTORE TEST RESULT ==="
if ($allPassed) {
    Write-Host "ALL CHECKS PASSED"
    $exitCode = 0
} else {
    Write-Host "SOME CHECKS FAILED"
    $exitCode = 1
}
Write-Host "Notes: $($notes -join '; ')"

# Alert on failure
if (-not $allPassed) {
    Write-Host "`nFiring alert..."
    try {
        & "$PSScriptRoot\monitor\alert_dispatcher.ps1" `
            -Level "error" `
            -Title "OLP XDV Restore Test FAILED" `
            -Body "Monthly restore test failed. Checks: $($notes -join '; ')" `
            -Tags "dr,restore-test-failed" `
            -EnvPath "$RepoRoot\.env"
    } catch {
        Write-Warning "Alert dispatch failed: $_"
    }
}

# Cleanup
Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "`nDone. Exit code: $exitCode"
exit $exitCode