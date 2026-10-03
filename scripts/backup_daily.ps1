<#
.SYNOPSIS
    Daily backup of OLP XDV irreplaceable state with offsite replication.

.DESCRIPTION
    Archives the machine-only state that CANNOT be rebuilt from git:
      - .env (encrypted with openssl AES-256-CBC using BACKUP_ENC_KEY)
      - clv/clv_log.json (canonical CLV ledger)
      - logs/health_state.json (alert state)
      - logs/steward_state.json (steward probe state)
      - brain/olp.db (brain mirror — rebuildable but speeds restore)
      - output/boards/published/*.json (last 7 days)

    Retention: 14 daily + 4 weekly (Sunday) + 3 monthly (1st).
    Offsite: rclone copy to $Remote (optional; skips silently if not configured).

.PARAMETER DestDir
    Local backup directory (default: <repo>\backups).

.PARAMETER Remote
    rclone remote:path (default: from .env BACKUP_RCLONE_REMOTE).

.PARAMETER KeepDaily
    Number of daily backups to keep (default: 14).

.PARAMETER NoOffsite
    Skip rclone offsite copy even if configured.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\backup_daily.ps1
    powershell -ExecutionPolicy Bypass -File scripts\backup_daily.ps1 -NoOffsite
#>
param(
    [string]$DestDir = "",
    [string]$Remote = "",
    [int]$KeepDaily = 14,
    [switch]$NoOffsite
)

$ErrorActionPreference = "Stop"

# Resolve repo root (parent of scripts/)
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $DestDir) {
    $DestDir = Join-Path $RepoRoot "backups"
}

# Read .env for backup config (encryption key, rclone remote)
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
    Write-Error "BACKUP_ENC_KEY not set in .env — cannot encrypt .env. Aborting."
    exit 1
}

if (-not $Remote) {
    $Remote = $envVars["BACKUP_RCLONE_REMOTE"]
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupName = "olp-backup-$timestamp"
$workDir = Join-Path $DestDir $backupName
New-Item -ItemType Directory -Path $workDir -Force | Out-Null

# Staging area for plaintext files (to be zipped)
$staging = Join-Path $workDir "stage"
New-Item -ItemType Directory -Path $staging -Force | Out-Null

$filesToStage = @(
    @{ Src = Join-Path $RepoRoot "clv\clv_log.json";          Name = "clv_log.json" }
    @{ Src = Join-Path $RepoRoot "logs\health_state.json";     Name = "health_state.json" }
    @{ Src = Join-Path $RepoRoot "logs\steward_state.json";    Name = "steward_state.json" }
    @{ Src = Join-Path $RepoRoot "brain\olp.db";              Name = "olp.db" }
)

$staged = 0
foreach ($f in $filesToStage) {
    if (Test-Path $f.Src) {
        Copy-Item $f.Src (Join-Path $staging $f.Name) -Force
        Write-Host "Staged: $($f.Name)"
        $staged++
    } else {
        Write-Warning "MISSING (skipped): $($f.Src)"
    }
}

# Published boards: last 7 days only
$pubDir = Join-Path $RepoRoot "output\boards\published"
if (Test-Path $pubDir) {
    $cutoff = (Get-Date).AddDays(-7)
    $recent = Get-ChildItem $pubDir -Filter "*.json" |
        Where-Object { $_.LastWriteTime -ge $cutoff }
    if ($recent) {
        $pubStage = Join-Path $staging "published"
        New-Item -ItemType Directory -Path $pubStage -Force | Out-Null
        $recent | Copy-Item -Destination $pubStage -Force
        Write-Host "Staged: $($recent.Count) published board(s) (last 7 days)"
        $staged++
    }
}

# Caddy cert directory (if Let's Encrypt)
$caddyData = Join-Path $RepoRoot "data\caddy"
if (Test-Path $caddyData) {
    Copy-Item $caddyData (Join-Path $staging "caddy_data") -Recurse -Force
    Write-Host "Staged: Caddy data directory"
    $staged++
}

# Encrypt .env → stage as .env.enc
$envSrc = Join-Path $RepoRoot ".env"
if (Test-Path $envSrc) {
    $encOut = Join-Path $staging ".env.enc"
    # openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 -k <key> -in .env -out .env.enc
    & openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 `
        -k $encKey -in $envSrc -out $encOut 2>$null
    if ($LASTEXITCODE -eq 0 -and (Test-Path $encOut)) {
        Write-Host "Encrypted: .env → .env.enc"
        $staged++
    } else {
        Write-Error "openssl encryption of .env failed. Aborting."
        exit 1
    }
} else {
    Write-Warning "MISSING: .env — backup cannot proceed without secrets."
    exit 1
}

# Zip the staged directory
$zipPath = Join-Path $workDir "$backupName.zip"
Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath -Force
Write-Host "Created: $zipPath"

# Cleanup staging
Remove-Item $staging -Recurse -Force

# Retention: keep last N daily, prune older
$dailyBackups = Get-ChildItem $DestDir -Directory -Filter "olp-backup-*" |
    Sort-Object Name -Descending
$today = Get-Date
$weeklyKept = 0
$monthlyKept = 0
$kept = 0

foreach ($b in $dailyBackups) {
    $datePart = $b.Name -replace "olp-backup-", "" -replace "_.*", ""
    $bDate = [datetime]::ParseExact($datePart, "yyyyMMdd", $null)

    # Decide retention bucket
    $isSunday = ($bDate.DayOfWeek -eq [System.DayOfWeek]::Sunday)
    $isFirst = ($bDate.Day -eq 1)

    if ($kept -lt $KeepDaily) {
        # Keep as daily
        $kept++
        continue
    }

    if ($isFirst -and $monthlyKept -lt 3) {
        $monthlyKept++
        continue
    }

    if ($isSunday -and $weeklyKept -lt 4) {
        $weeklyKept++
        continue
    }

    # Otherwise prune
    Write-Host "Pruning old backup: $($b.Name)"
    Remove-Item $b.FullName -Recurse -Force
}

# Offsite copy (optional)
if (-not $NoOffsite -and $Remote) {
    Write-Host "Offsite: rclone copy to $Remote ..."
    & rclone copy $zipPath "$Remote/$backupName.zip" 2>&1 | ForEach-Object { Write-Host "  rclone: $_" }
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Offsite copy complete."
    } else {
        Write-Warning "rclone offsite copy failed (exit $LASTEXITCODE) — local backup intact."
    }
} else {
    Write-Host "Offsite copy skipped (NoOffsite or no remote configured)."
}

Write-Host "`nBackup complete: $zipPath"
Write-Host "  Files staged: $staged"
Write-Host "  Local retention: $KeepDaily daily, 4 weekly, 3 monthly"