# OLP XDV - register the 03:00 daily FlashScore fixtures scrape as a Task Scheduler task.
#
# Runs scrape_flashscore_daily.bat every day at 03:00 as the current user.
# Idempotent: re-running replaces the task with the same definition.
#
# Run (ADMIN): powershell -NoProfile -ExecutionPolicy Bypass -File setup_flashscore_scraper_task.ps1
# Requires an elevated shell: the task is admin-owned (RunLevel Highest) to match
# the other daily tasks, so Set-ScheduledTask without elevation returns 0x80070005.
#
# The scraper pulls ALL whitelisted leagues (upcoming rounds = 2-day+ advance
# fixture data) into data/live_odds/flashscore_odds_<timestamp>.jsonl, which feeds
# the verification gate and daily board's fixture window.

$ErrorActionPreference = "Stop"

# Hard gate: must run elevated or Set-ScheduledTask silently fails with
# 0x80070005 and the task stays broken while the script "succeeds" partway.
$isElevated = ([System.Security.Principal.WindowsPrincipal][System.Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isElevated) {
    Write-Error "NOT elevated - run this from an ADMIN PowerShell (right-click > Run as administrator)."
    exit 1
}

$proj   = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat    = Join-Path $proj "scrape_flashscore_daily.bat"
$task   = "OLP XDV FlashScore Scraper"
$time   = "03:00"

if (-not (Test-Path $bat)) { Write-Error "scrape_flashscore_daily.bat not found at $bat"; exit 1 }

# CRITICAL: the project folder contains a space ("omniroute test"). Passing the
# .bat path straight to -Execute makes Task Scheduler split it at the space, so
# the task tries to run "C:\...\omniroute" and fails 0x80070002 (file not found).
# The robust form runs cmd.exe and passes the full path as ONE double-quoted
# argument, plus a WorkingDirectory so relative paths resolve.
$action  = New-ScheduledTaskAction `
    -Execute "C:\Windows\System32\cmd.exe" `
    -Argument ('/c ""' + $bat + '""') `
    -WorkingDirectory $proj
$trigger = New-ScheduledTaskTrigger -Daily -At $time
# Hardened settings (matches the other daily tasks): reboot-survival +
# restart-on-failure, never killed for running long. ExecutionTimeLimit 0 = no limit.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -MultipleInstances IgnoreNew `
    -Priority 7
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

$exists = Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
if ($exists) {
    Write-Host "Task '$task' exists - updating..."
    Set-ScheduledTask -TaskName $task -Trigger $trigger -Action $action -Settings $settings -Principal $principal
} else {
    Write-Host "Registering new task '$task'..."
    Register-ScheduledTask -TaskName $task -Trigger $trigger -Action $action -Settings $settings -Principal $principal -Force
}

# Verify the stored action is intact (no space-split) before trusting it.
$t = Get-ScheduledTask -TaskName $task
foreach ($a in $t.Actions) {
    Write-Host "Execute: $($a.Execute)"
    Write-Host "Arguments: $($a.Arguments)"
    Write-Host "WorkingDirectory: $($a.WorkingDirectory)"
}
Write-Host "State: $($t.State)"
Write-Host "NextRunTime: $(( $t | Get-ScheduledTaskInfo ).NextRunTime)"
