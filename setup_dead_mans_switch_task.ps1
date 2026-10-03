param(
    [string]$TaskName = "OLP XDV Daily Run Dead Man's Switch",
    [string]$Time = "08:15"
)

# Idempotent registration of the dead-man's-switch task.
# Runs ~08:15 (after the 07:00 daily run slot) to verify the run completed.
# Run this script after any repo move, or when Task Scheduler needs resetting.

$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat  = Join-Path $proj "dead_mans_switch.bat"

if (-not (Test-Path $bat)) { Write-Error "dead_mans_switch.bat not found at $bat"; exit 1 }

# Check if task exists
$exists = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($exists) {
    Write-Host "Task '$TaskName' exists — updating trigger and action..."
    $trigger = New-ScheduledTaskTrigger -Daily -At $Time
    $action  = New-ScheduledTaskAction -Execute $bat
    Set-ScheduledTask -TaskName $TaskName -Trigger $trigger -Action $action -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries)
    Write-Host "Updated."
} else {
    Write-Host "Registering new task '$TaskName'..."
    $trigger = New-ScheduledTaskTrigger -Daily -At $Time
    $action  = New-ScheduledTaskAction -Execute $bat
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $TaskName -Trigger $trigger -Action $action -Settings $settings -RunLevel Highest
    Write-Host "Registered. Next run at $Time."
}

# Verify
$task = Get-ScheduledTask -TaskName $TaskName
Write-Host "State: $($task.State)"
Write-Host "NextRunTime: $($task.NextRunTime)"