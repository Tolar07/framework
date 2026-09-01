# OLP XDV - register the Results Verification Agent as a Task Scheduler task.
# Runs daily at 22:00 to grade predictions against real results.
# Run (ADMIN): powershell -NoProfile -ExecutionPolicy Bypass -File setup_grade_results_task.ps1
# Requires an elevated shell: the existing task is admin-owned (RunLevel Highest),
# so Set-ScheduledTask without elevation returns 0x80070005.

$ErrorActionPreference = "Stop"

# Hard gate: this must run elevated or Set-ScheduledTask silently fails with
# 0x80070005 and the task stays broken while the script "succeeds" partway.
# A SID ending -500 is the built-in Administrator; -12288 is High integrity.
$isElevated = ([System.Security.Principal.WindowsPrincipal][System.Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isElevated) {
    Write-Error "NOT elevated - run this from an ADMIN PowerShell (right-click > Run as administrator)."
    exit 1
}

$proj   = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat    = Join-Path $proj "grade_results.bat"

if (-not (Test-Path $bat)) { Write-Error "grade_results.bat not found at $bat"; exit 1 }

# ===== TASK: RESULTS VERIFICATION (22:00) =====
$taskName  = "OLP XDV Results Verification"
$time      = "22:00"
$args      = '/c ""' + $bat + '""'

if (-not (Test-Path $bat)) { Write-Error "grade_results.bat not found at $bat"; exit 1 }

# CRITICAL: the project folder contains a space ("omniroute test"). Passing the
# .bat path straight to -Execute makes Task Scheduler split it at the space, so
# the task tries to run "C:\...\omniroute" and fails 0x80070002 (file not found)
# every morning. The robust form runs cmd.exe and passes the full path as ONE
# double-quoted argument, plus a WorkingDirectory so relative
# paths in the .bat file work.
$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $args -WorkingDirectory $proj

# Run whether user is logged on or not, with highest privileges
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Trigger: Daily at 22:00
$trigger = New-ScheduledTaskTrigger -Daily -At $time

# Register the task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal `
    -Description "Grades OLP XDV predictions against real results, tracks win/loss record and CLV" `
    -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)) `
    -Force

Write-Host "Successfully registered scheduled task: $taskName"
Write-Host "Trigger: Daily at $time"
Write-Host "Action: $bat"