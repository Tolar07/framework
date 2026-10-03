# OLP XDV - install the web dashboard server as a STARTUP service.
#
# The dashboard was previously only started by hand (start_server.bat or
# webapp/_restart_server.py), so after any reboot it stayed down until someone
# opened it. This installs a Startup-folder shortcut (dashboard_hidden.vbs ->
# start_dashboard.bat -> webapp/server.py --host 0.0.0.0 --port 8088) that
# brings the board back up at every logon with NO admin rights — same pattern
# as the Telegram daemon (setup_poller_daemon.ps1).
#
# The server is single-instance by design: if the port is already bound, the
# new process exits with an honest log line, so the Startup entry can never
# double-serve.
#
# Run with:
#   powershell -NoProfile -ExecutionPolicy Bypass -File webapp\setup_dashboard_autostart.ps1
# Idempotent: re-running refreshes the shortcut and (re)starts the server.

$ErrorActionPreference = "Stop"
$proj   = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$vbs    = Join-Path $proj "webapp\dashboard_hidden.vbs"
$startup = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$lnk    = Join-Path $startup "OLP XDV Dashboard.lnk"

if (-not (Test-Path $vbs)) { throw "missing $vbs" }

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = Join-Path $env:WINDIR "System32\wscript.exe"
$sc.Arguments = "`"$vbs`""
$sc.WorkingDirectory = $proj
$sc.Save()
Write-Host "Startup shortcut: $lnk"

# (Re)start it now so the board is reachable immediately. The new process
# binds 0.0.0.0:8088; if an old server still holds the port, the bind fails
# with an honest log line and the old one keeps serving (single-instance).
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*webapp\server.py --host 0.0.0.0*" -or
    $_.CommandLine -like "*webapp/server.py --host 0.0.0.0*"
} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Start-Process wscript.exe -ArgumentList "`"$vbs`"" -WindowStyle Hidden
Write-Host "Dashboard started hidden on 0.0.0.0:8088 (logs\web_server.log)"
