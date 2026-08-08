# OLP XDV - register the 07:00 daily board run as a Task Scheduler task.
# Run: powershell -NoProfile -ExecutionPolicy Bypass -File setup_daily_board_task.ps1

$ErrorActionPreference = "Stop"
$proj   = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat    = Join-Path $proj "run_daily.bat"
$task   = "OLP XDV Daily Board"
$time   = "07:00"

if (-not (Test-Path $bat)) { Write-Error "run_daily.bat not found at $bat"; exit 1 }

# Quote the bat path because the folder contains a space (omniroute test)
$action  = New-ScheduledTaskAction -Execute $bat
$trigger = New-ScheduledTaskTrigger -Daily -At $time
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

$exists = Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
if ($exists) {
    Write-Host "Task '$task' exists — updating..."
    Set-ScheduledTask -TaskName $task -Trigger $trigger -Action $action -Settings $settings -Principal $principal
} else {
    Write-Host "Registering new task '$task'..."
    Register-ScheduledTask -TaskName $task -Trigger $trigger -Action $action -Settings $settings -Principal $principal -Force
}

$task = Get-ScheduledTask -TaskName $task
Write-Host "State: $($task.State)"
Write-Host "NextRunTime: $($task.NextRunTime)"