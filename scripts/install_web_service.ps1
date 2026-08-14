<#
.SYNOPSIS
    Install the OLP XDV web tier (Python + Caddy) as a Windows service via NSSM.

.DESCRIPTION
    Wraps scripts\run_web_tier.bat as a Windows service named "OLP XDV Web"
    with automatic restart on failure. NSSM must be installed (scoop/choco).

    The service runs as SYSTEM by default (no interactive session needed).
    For Let's Encrypt, the service must be able to bind :443 — on Windows
    this requires either:
      - Run as Administrator (elevated)
      - Or: `netsh http add urlacl url=https://+:443/ user=SYSTEM`

.PARAMETER NssmPath
    Path to nssm.exe (default: looks in PATH).

.PARAMETER ServiceName
    Service display name (default: "OLP XDV Web").

.PARAMETER InstallDir
    Path to repo root (default: script parent's parent).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\install_web_service.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\install_web_service.ps1 -ServiceName "OLP XDV Web Prod"
#>
param(
    [string]$NssmPath = "nssm",
    [string]$ServiceName = "OLP XDV Web",
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"

# Resolve repo root
if (-not $InstallDir) {
    $InstallDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
$RepoRoot = Resolve-Path $InstallDir

Write-Host "OLP XDV Web Service Installer"
Write-Host "Repo root: $RepoRoot"
Write-Host "Service:   $ServiceName"

# Check NSSM
$nssm = $NssmPath
if (-not (Get-Command $nssm -ErrorAction SilentlyContinue)) {
    Write-Error "NSSM not found in PATH. Install it first:"
    Write-Error "  scoop install nssm"
    Write-Error "  OR"
    Write-Error "  choco install nssm"
    exit 1
}

# Check the run script exists
$runScript = Join-Path $RepoRoot "scripts\run_web_tier.bat"
if (-not (Test-Path $runScript)) {
    Write-Error "run_web_tier.bat not found at $runScript"
    exit 1
}

# Check Caddy
if (-not (Get-Command caddy -ErrorAction SilentlyContinue)) {
    Write-Warning "Caddy not found in PATH. Install it for HTTPS:"
    Write-Warning "  scoop install caddy"
    Write-Warning "  OR"
    Write-Warning "  choco install caddy"
    # Don't exit — the service will fail visibly if Caddy is missing
}

# Check Python
$pyPath = "C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $pyPath)) {
    Write-Warning "Python 3.12 not found at expected path. Ensure 'py' launcher works."
}

# Install the service
Write-Host "`nInstalling service '$ServiceName'..."

# Remove existing service if present
$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing service..."
    & $nssm stop $ServiceName -Confirm:$false 2>$null
    & $nssm remove $ServiceName confirm
}

# Install
& $nssm install $ServiceName "cmd.exe" "/c `"$runScript`""
if ($LASTEXITCODE -ne 0) {
    Write-Error "nssm install failed"
    exit 1
}

# Configure service
& $nssm set $ServiceName DisplayName $ServiceName
& $nssm set $ServiceName Description "OLP XDV web dashboard (Python + Caddy reverse proxy). Auto-restart on crash."
& $nssm set $ServiceName Start SERVICE_AUTO_START
& $nssm set $ServiceName AppDirectory $RepoRoot
& $nssm set $ServiceName AppStdout (Join-Path $RepoRoot "logs\web_service_stdout.log")
& $nssm set $ServiceName AppStderr (Join-Path $RepoRoot "logs\web_service_stderr.log")
& $nssm set $ServiceName AppRotateFiles 1
& $nssm set $ServiceName AppRotateOnline 1
& $nssm set $ServiceName AppRotateBytes 10485760  # 10 MB

# Restart policy: restart on failure (exit code != 0)
& $nssm set $ServiceName AppExit Default Restart
& $nssm set $ServiceName AppThrottle 5000  # 5s between restarts

# Ensure logs directory exists
$logsDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}

# Start the service
Write-Host "Starting service..."
& $nssm start $ServiceName
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Service start returned non-zero (may still be starting). Check logs."
}

# Verify
Start-Sleep -Seconds 3
$status = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($status) {
    Write-Host "`nService status: $($status.Status)"
    Write-Host "Start type:   $($status.StartType)"
} else {
    Write-Warning "Service not found after install."
}

Write-Host "`nDone. Verify with:"
Write-Host "  Get-Service '$ServiceName' | Select-Object Status, StartType"
Write-Host "  Get-Content '$(Join-Path $RepoRoot "logs\web_server.log")' -Tail 20"
Write-Host "`nTo test restart: Stop-Service '$ServiceName'; Start-Sleep 10; Get-Service '$ServiceName'"