# OLP XDV - register the fixture watcher as a Task Scheduler task.
#
# Runs fixture_watcher.bat every 1 hour as the current user. Idempotent:
# re-running replaces the task with the same definition. No admin required
# for a current-user, RunLevel Limited task.
#
# Run with:
#   powershell -NoProfile -ExecutionPolicy Bypass -File setup_fixture_watcher_task.ps1

$ErrorActionPreference = "Stop"
$proj   = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat    = Join-Path $proj "fixture_watcher.bat"
$task   = "OLP XDV Fixture Watcher"

$action     = New-ScheduledTaskAction -Execute $bat
$trigger    = New-ScheduledTaskTrigger -Once -At (Get-Date) `
                -RepetitionInterval (New-TimeSpan -Minutes 60) `
                -RepetitionDuration (New-TimeSpan -Days 365)
# StopAtDurationEnd defaulted to True and, with an empty Duration, can kill
# the repetition. Force it off so the 1h cadence is truly indefinite.
$trigger.Repetition.StopAtDurationEnd = $false
# The default settings DISALLOW starting on battery - a fixture watcher must
# run whenever the machine is on, plugged in or not.
$settings   = New-ScheduledTaskSettingsSet -StartWhenAvailable `
                -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal  = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
                -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null

$t = Get-ScheduledTask -TaskName $task
Write-Host "Task '$task' registered."
Write-Host ("  State   : {0}" -f $t.State)
Write-Host ("  Trigger : every 60 min, indefinite" )