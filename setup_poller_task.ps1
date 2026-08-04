# OLP XDV - register the Telegram command poller as a Task Scheduler task.
#
# Runs telegram_poll_once.bat every minute as the current user. Idempotent:
# re-running replaces the task with the same definition. No admin required for
# a current-user, RunLevel Limited task.
#
# One minute keeps command latency to at most ~1 min without needing a
# permanently-open window. If you want near-instant replies instead, run
# telegram_poller.bat (--loop daemon) and leave its window open.
#
# Run with:
#   powershell -NoProfile -ExecutionPolicy Bypass -File setup_poller_task.ps1

$ErrorActionPreference = "Stop"
$proj   = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat    = Join-Path $proj "telegram_poll_once.bat"
$task   = "OLP XDV Telegram Poller"

$action     = New-ScheduledTaskAction -Execute $bat
$trigger    = New-ScheduledTaskTrigger -Once -At (Get-Date) `
                -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings   = New-ScheduledTaskSettingsSet -StartWhenAvailable `
                -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
$principal  = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
                -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null

$t = Get-ScheduledTask -TaskName $task
Write-Host "Task '$task' registered."
Write-Host ("  State   : {0}" -f $t.State)
Write-Host ("  Trigger : every {0} min, next boundary {1}" -f `
    $trigger.Repetition.Interval, $trigger.StartBoundary)
Write-Host ("  Action  : {0}" -f $bat)
