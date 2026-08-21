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
$script = Join-Path $proj "scripts" "hourly-fixture-check.js"
$task   = "OLP XDV Hourly Fixture Check"

if (-not (Test-Path $script)) { Write-Error "hourly-fixture-check.js not found at $script"; exit 1 }

# CRITICAL: the project folder contains a space ("omniroute test").
# Use cmd.exe to run node with the full script path as ONE double-quoted argument.
$action  = New-ScheduledTaskAction `
    -Execute "C:\Windows\System32\cmd.exe" `
    -Argument ('/c "node "' + $script + '" 2>&1 >> "' + (Join-Path $proj "logs" "hourly-fixture-check" "scheduler-wrapper.log") + '"') `
    -WorkingDirectory $proj

# Run every hour, starting at the top of the next hour
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddHours(1).ToString("HH:mm") -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration ([TimeSpan]::MaxValue)
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