# OLP XDV - register the Data Steward (06:00 pre-board + 15:00 afternoon
# refresh) as a Task Scheduler task.
# Run (ADMIN): powershell -NoProfile -ExecutionPolicy Bypass -File setup_steward_task.ps1
# Requires an elevated shell: the existing daily task is admin-owned (RunLevel
# Highest), so Set-ScheduledTask without elevation returns 0x80070005.

$ErrorActionPreference = "Stop"

# Hard gate: this must run elevated or Set-ScheduledTask silently fails with
# 0x80070005 and the task stays broken while the script "succeeds" partway.
$isElevated = ([System.Security.Principal.WindowsPrincipal][System.Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isElevated) {
    Write-Error "NOT elevated - run this from an ADMIN PowerShell (right-click > Run as administrator)."
    exit 1
}

$proj   = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat    = Join-Path $proj "steward.bat"
$task   = "OLP XDV Data Steward"
$times  = @("06:00", "15:00")   # pre-board + afternoon refresh for evening fixtures

if (-not (Test-Path $bat)) { Write-Error "steward.bat not found at $bat"; exit 1 }

# CRITICAL: the project folder contains a space ("omniroute test"). Passing the
# .bat path straight to -Execute makes Task Scheduler split it at the space, so
# the task tries to run "C:\...\omniroute" and fails 0x80070002 every time.
# The robust form runs cmd.exe and passes the full path as ONE double-quoted
# argument, plus a WorkingDirectory so relative paths resolve (same as the
# daily-board task).
$action  = New-ScheduledTaskAction `
    -Execute "C:\Windows\System32\cmd.exe" `
    -Argument ('/c ""' + $bat + '""') `
    -WorkingDirectory $proj
$triggers = @()
foreach ($t in $times) {
    $triggers += New-ScheduledTaskTrigger -Daily -At $t
}
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

$exists = Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
if ($exists) {
    Write-Host "Task '$task' exists - updating..."
    Set-ScheduledTask -TaskName $task -Trigger $triggers -Action $action -Settings $settings -Principal $principal
} else {
    Write-Host "Registering new task '$task'..."
    Register-ScheduledTask -TaskName $task -Trigger $triggers -Action $action -Settings $settings -Principal $principal -Force
}

# Verify the stored action is intact (no space-split) before trusting it.
$t = Get-ScheduledTask -TaskName $task
foreach ($a in $t.Actions) {
    Write-Host "Execute: $($a.Execute)"
    Write-Host "Arguments: $($a.Arguments)"
    Write-Host "WorkingDirectory: $($a.WorkingDirectory)"
}
Write-Host "Triggers: $((($t.Triggers | ForEach-Object { $_.StartBoundary }) -join ', '))"
Write-Host "State: $($t.State)"
Write-Host "NextRunTime: $(( $t | Get-ScheduledTaskInfo ).NextRunTime)"
