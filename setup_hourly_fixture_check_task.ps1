# OLP XDV - register the HOURLY fixture check as a Task Scheduler task.
# Run (ADMIN): powershell -NoProfile -ExecutionPolicy Bypass -File setup_hourly_fixture_check_task.ps1
# Requires an elevated shell: the task runs with highest privileges.

$ErrorActionPreference = "Stop"

# Hard gate: this must run elevated or Set-ScheduledTask silently fails with
# 0x80070005 and the task stays broken while the script "succeeds" partway.
$isElevated = ([System.Security.Principal.WindowsPrincipal][System.Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isElevated) {
    Write-Error "NOT elevated - run this from an ADMIN PowerShell (right-click > Run as administrator)."
    exit 1
}

$proj   = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptsDir = Join-Path $proj "scripts"
$script = Join-Path $scriptsDir "hourly-fixture-check.js"
$logsDir = Join-Path $proj "logs"
$hourlyLogsDir = Join-Path $logsDir "hourly-fixture-check"
$wrapperLog = Join-Path $hourlyLogsDir "scheduler-wrapper.log"
$task   = "OLP XDV Daily Result Verification"

if (-not (Test-Path $script)) { Write-Error "hourly-fixture-check.js not found at $script"; exit 1 }

# CRITICAL: the project folder contains a space ("omniroute test").
# Use cmd.exe to run node with the full script path as ONE double-quoted argument.
$action  = New-ScheduledTaskAction `
    -Execute "C:\Windows\System32\cmd.exe" `
    -Argument ('/c "node "' + $script + '" 2>&1 >> "' + $wrapperLog + '"') `
    -WorkingDirectory $proj

# Run daily at 22:00
$trigger = New-ScheduledTaskTrigger -Daily -At "22:00"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

$exists = Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
if ($exists) {
    Write-Host "Task '$task' exists - updating..."
    Set-ScheduledTask -TaskName $task -Trigger $trigger -Action $action -Settings $settings -Principal $principal
} else {
    Write-Host "Registering new task '$task'..."
    Register-ScheduledTask -TaskName $task -Trigger $trigger -Action $action -Settings $settings -Principal $principal -Force
}

# Verify the stored action is intact
$t = Get-ScheduledTask -TaskName $task
foreach ($a in $t.Actions) {
    Write-Host "Execute: $($a.Execute)"
    Write-Host "Arguments: $($a.Arguments)"
    Write-Host "WorkingDirectory: $($a.WorkingDirectory)"
}
Write-Host "State: $($t.State)"
Write-Host "NextRunTime: $(( $t | Get-ScheduledTaskInfo ).NextRunTime)"