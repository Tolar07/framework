# OLP XDV - register the two daily tasks as Task Scheduler tasks.
# Stage 1 (20:00): Pre-fetch and cache all external data (--prefetch-only)
# Stage 2 (22:00): Read from cache, run models, generate board, send to Telegram
# Run (ADMIN): powershell -NoProfile -ExecutionPolicy Bypass -File setup_daily_board_task.ps1
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
$bat    = Join-Path $proj "run_daily.bat"

# ===== TASK 1: PREFETCH (20:00) =====
$task1  = "OLP XDV Daily Prefetch"
$time1  = "20:00"
$args1  = '/c ""' + $bat + ' --prefetch-only""'

# ===== TASK 2: INSTANT DISPATCH (22:00) =====
$task2  = "OLP XDV Daily Board"
$time2  = "22:00"
$args2  = '/c ""' + $bat + '""'

if (-not (Test-Path $bat)) { Write-Error "run_daily.bat not found at $bat"; exit 1 }

# CRITICAL: the project folder contains a space ("omniroute test"). Passing the
# .bat path straight to -Execute makes Task Scheduler split it at the space, so
# the task tries to run "C:\...\omniroute" and fails 0x80070002 (file not found)
# every morning. The robust form runs cmd.exe and passes the full path as ONE
# double-quoted argument, plus a WorkingDirectory so relative paths resolve.
$action1  = New-ScheduledTaskAction `
    -Execute "C:\Windows\System32\cmd.exe" `
    -Argument $args1 `
    -WorkingDirectory $proj
$trigger1 = New-ScheduledTaskTrigger -Daily -At $time1
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

$action2  = New-ScheduledTaskAction `
    -Execute "C:\Windows\System32\cmd.exe" `
    -Argument $args2 `
    -WorkingDirectory $proj
$trigger2 = New-ScheduledTaskTrigger -Daily -At $time2

# --- Register/Update Task 1: Prefetch ---
$exists1 = Get-ScheduledTask -TaskName $task1 -ErrorAction SilentlyContinue
if ($exists1) {
    Write-Host "Task '$task1' exists - updating..."
    Set-ScheduledTask -TaskName $task1 -Trigger $trigger1 -Action $action1 -Settings $settings -Principal $principal
} else {
    Write-Host "Registering new task '$task1'..."
    Register-ScheduledTask -TaskName $task1 -Trigger $trigger1 -Action $action1 -Settings $settings -Principal $principal -Force
}

# --- Register/Update Task 2: Board Dispatch ---
$exists2 = Get-ScheduledTask -TaskName $task2 -ErrorAction SilentlyContinue
if ($exists2) {
    Write-Host "Task '$task2' exists - updating..."
    Set-ScheduledTask -TaskName $task2 -Trigger $trigger2 -Action $action2 -Settings $settings -Principal $principal
} else {
    Write-Host "Registering new task '$task2'..."
    Register-ScheduledTask -TaskName $task2 -Trigger $trigger2 -Action $action2 -Settings $settings -Principal $principal -Force
}

# Verify both tasks
Write-Host "`n=== VERIFICATION ==="
foreach ($tname in @($task1, $task2)) {
    $t = Get-ScheduledTask -TaskName $tname
    Write-Host "`nTask: $tname"
    foreach ($a in $t.Actions) {
        Write-Host "  Execute: $($a.Execute)"
        Write-Host "  Arguments: $($a.Arguments)"
        Write-Host "  WorkingDirectory: $($a.WorkingDirectory)"
    }
    Write-Host "  State: $($t.State)"
    Write-Host "  NextRunTime: $(( $t | Get-ScheduledTaskInfo ).NextRunTime)"
}