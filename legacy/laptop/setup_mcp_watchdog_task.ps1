# OLP XDV - register the MCP watchdog as a Task Scheduler task.
#
# Runs mcp_watchdog.bat every 30 minutes as the current user. Idempotent:
# re-running replaces the task with the same definition. No admin required
# for a current-user, RunLevel Limited task.
#
# The 30min cadence keeps MCP connectivity awareness fresh without excessive
# overhead. The dedicated watchdog is the primary alerting path for MCP drops,
# complementing the 2-hourly health monitor's best-effort MCP probe.
#
# Run with:
#   powershell -NoProfile -ExecutionPolicy Bypass -File setup_mcp_watchdog_task.ps1

$ErrorActionPreference = "Stop"
$proj   = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat    = Join-Path $proj "mcp_watchdog.bat"
$task   = "OLP XDV MCP Watchdog"

$action     = New-ScheduledTaskAction -Execute $bat
$trigger    = New-ScheduledTaskTrigger -Once -At (Get-Date) `
                -RepetitionInterval (New-TimeSpan -Minutes 30) `
                -RepetitionDuration (New-TimeSpan -Days 365)
# StopAtDurationEnd defaulted to True and, with an empty Duration, can kill
# the repetition. Force it off so the 30min cadence is truly indefinite.
$trigger.Repetition.StopAtDurationEnd = $false
# The default settings DISALLOW starting on battery - a watchdog must
# run whenever the machine is on, plugged in or not.
$settings   = New-ScheduledTaskSettingsSet -StartWhenAvailable `
                -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal  = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
                -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null

$t = Get-ScheduledTask -TaskName $task
Write-Host "Task '$task' registered."
Write-Host ("  State   : {0}" -f $t.State)
Write-Host ("  Trigger : every 30 min, indefinite" )