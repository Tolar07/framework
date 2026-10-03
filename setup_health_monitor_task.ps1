# OLP XDV - register the health monitor as a Task Scheduler task.
#
# Runs health_monitor.bat every 2 hours as the current user. Idempotent:
# re-running replaces the task with the same definition. No admin required
# for a current-user, RunLevel Limited task.
#
# The 2h cadence keeps issue latency low without hammering the free-tier odds
# quota (the quota probe reads an API counter, it does not spend quota; the
# only network the monitor spends is Telegram alerts + a dashboard liveness
# check on localhost). The 07:00 daily run has its own task; this monitor
# complements it - it answers "is the pipeline healthy" even on days the
# daily run itself is the thing that failed.
#
# Run with:
#   powershell -NoProfile -ExecutionPolicy Bypass -File setup_health_monitor_task.ps1

$ErrorActionPreference = "Stop"
$proj   = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat    = Join-Path $proj "health_monitor.bat"
$task   = "OLP XDV Health Monitor"

$action     = New-ScheduledTaskAction -Execute $bat
$trigger    = New-ScheduledTaskTrigger -Once -At (Get-Date) `
                -RepetitionInterval (New-TimeSpan -Minutes 120) `
                -RepetitionDuration (New-TimeSpan -Days 365)
# StopAtDurationEnd defaulted to True and, with an empty Duration, can kill
# the repetition. Force it off so the 2h cadence is truly indefinite.
$trigger.Repetition.StopAtDurationEnd = $false
# The default settings DISALLOW starting on battery - a health monitor must
# run whenever the machine is on, plugged in or not.
$settings   = New-ScheduledTaskSettingsSet -StartWhenAvailable `
                -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal  = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
                -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null

$t = Get-ScheduledTask -TaskName $task
Write-Host "Task '$task' registered."
Write-Host ("  State   : {0}" -f $t.State)
Write-Host ("  Trigger : every 120 min, indefinite" )
