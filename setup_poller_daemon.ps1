# OLP XDV - install the Telegram command poller as a RESIDENT DAEMON.
#
# Near-instant replies: one long-lived process (telegram_commands.py --loop)
# blocks on Telegram long-polling, so a message is answered within seconds.
#
# This installs into the CURRENT USER'S STARTUP FOLDER (a .lnk that runs
# telegram_poller_hidden.vbs hidden) so it starts at every logon with NO
# admin rights. Task Scheduler's AtLogOn trigger requires elevation, which
# is why this avoids Task Scheduler entirely for the daemon.
#
# The daemon is self-healing (catches and continues past transient errors)
# and single-instance (a pid lock refuses a second copy, so it can never
# double-answer by racing on the getUpdates offset).
#
# Run with:
#   powershell -NoProfile -ExecutionPolicy Bypass -File setup_poller_daemon.ps1
# Idempotent: re-running refreshes the shortcut and (re)starts the daemon.

$ErrorActionPreference = "Stop"
$proj   = Split-Path -Parent $MyInvocation.MyCommand.Path
$vbs    = Join-Path $proj "telegram_poller_hidden.vbs"
$startup = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$lnk    = Join-Path $startup "OLP XDV Telegram Daemon.lnk"

if (-not (Test-Path $vbs)) { throw "missing $vbs" }

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = Join-Path $env:WINDIR "System32\wscript.exe"
$sc.Arguments = "`"$vbs`""
$sc.WorkingDirectory = $proj
$sc.Save()
Write-Host "Startup shortcut: $lnk"

# (Re)start it now so near-instant replies begin immediately. The single-
# instance lock in telegram_commands.py makes a duplicate a no-op.
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*telegram_commands.py --loop*"
} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Start-Process wscript.exe -ArgumentList "`"$vbs`"" -WindowStyle Hidden
Write-Host "Daemon started."
