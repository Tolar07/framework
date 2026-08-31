<#
.SYNOPSIS
    Registers the API-Football Verification scheduled task for OLP XDV.

.DESCRIPTION
    Creates a daily Task Scheduler job that runs the API-Football verification
    script to fetch and verify match results for the daily result loop.

    Task Name: "OLP XDV API-Football Verification"
    Schedule: Daily at 22:00 (after matches finish)
    Run Level: Highest (admin)
    Reboot Survival: Yes (StartWhenAvailable)
    Restart on Failure: 3 retries, 5 minutes apart

.PARAMETER DryRun
    Show what would be created without actually registering the task.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup_verification_task.ps1
    powershell -ExecutionPolicy Bypass -File setup_verification_task.ps1 -DryRun
#>
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# Must be elevated to create/modify scheduled tasks
$isElevated = ([System.Security.Principal.WindowsPrincipal][System.Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isElevated) {
    Write-Error "NOT elevated - run from an ADMIN PowerShell."
    exit 1
}

$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
$batPath = Join-Path $proj "scripts\api_football_verification.bat"

if (-not (Test-Path $batPath)) {
    Write-Error "BAT wrapper not found at $batPath"
    exit 1
}

$taskName = "OLP XDV API-Football Verification"
$triggerTime = "22:00"  # After matches typically finish

Write-Host "Setting up task: $taskName"
Write-Host "Script: $batPath"
Write-Host "Schedule: Daily at $triggerTime"
Write-Host ""

if ($DryRun) {
    Write-Host "[DRY RUN] Would create task with:"
    Write-Host "  - Action: cmd.exe /c `"$batPath`""
    Write-Host "  - Trigger: Daily at $triggerTime"
    Write-Host "  - Settings: StartWhenAvailable, RestartCount=3, RestartInterval=5min, ExecutionTimeLimit=0"
    Write-Host "  - Principal: Interactive, Highest"
    exit 0
}

# Define the action (cmd.exe /c "full path to bat")
$action = New-ScheduledTaskAction `
    -Execute "C:\Windows\System32\cmd.exe" `
    -Argument ('/c ""' + $batPath + '""') `
    -WorkingDirectory $proj

# Trigger: Daily at 22:00
$trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime

# Hardened settings: reboot-survival + restart-on-failure
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -MultipleInstances IgnoreNew `
    -Priority 7

# Principal: interactive + highest (matches existing security model)
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest

# Register the task
try {
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Force `
        -ErrorAction Stop

    Write-Host "`n✅ Task '$taskName' registered successfully."
    Write-Host "   Schedule: Daily at $triggerTime"
    Write-Host "   Hardening: RestartCount=3, RestartInterval=5m, StartWhenAvailable=on"
    Write-Host ""
    Write-Host "Verify with:"
    Write-Host "  Get-ScheduledTask -TaskName '$taskName' | Format-List TaskName, State, Triggers"
    Write-Host "  Get-ScheduledTask -TaskName '$taskName' | Select-Object -ExpandProperty Settings"
} catch {
    Write-Error "FAILED to register '$taskName': $_"
    exit 1
}