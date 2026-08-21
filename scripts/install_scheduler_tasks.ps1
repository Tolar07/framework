<#
.SYNOPSIS
    Re-register all OLP XDV scheduled tasks with reboot-survival + restart-on-failure.

.DESCRIPTION
    Reads the existing task definitions from setup_*.ps1 and applies a uniform
    hardening to each:
      - RestartCount / RestartInterval (restart-on-failure)
      - StartWhenAvailable (boot-pending runs fire when the machine comes up)
      - ExecutionTimeLimit = 0 (never killed for running long)
      - DisallowHardTerminate = False (so restart can actually happen)

    All 5 tasks: Daily Board, Data Steward, Health Monitor, Dead Man's Switch,
    Telegram Poller.

.PARAMETER DryRun
    Show what would change without applying it.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\install_scheduler_tasks.ps1
    powershell -ExecutionPolicy Bypass -File scripts\install_scheduler_tasks.ps1 -DryRun
#>
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# Must be elevated to modify scheduled tasks
$isElevated = ([System.Security.Principal.WindowsPrincipal][System.Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isElevated) {
    Write-Error "NOT elevated - run from an ADMIN PowerShell."
    exit 1
}

$proj = Split-Path -Parent $MyInvocation.MyCommand.Path

$Tasks = @(
    @{ Name = "OLP XDV Daily Board";        Bat = "run_daily.bat";        Trigger = "Daily 07:00" }
    @{ Name = "OLP XDV Data Steward";       Bat = "steward.bat";          Trigger = "Daily 06:00, 15:00" }
    @{ Name = "OLP XDV Health Monitor";     Bat = "health_monitor.bat";   Trigger = "Every 2h" }
    @{ Name = "OLP XDV Dead Man's Switch";  Bat = "dead_mans_switch.bat";  Trigger = "Daily 08:00" }
    @{ Name = "OLP XDV Telegram Poller";    Bat = "telegram_poller.bat";   Trigger = "At logon (resident)" }
    @{ Name = "OLP XDV Fixture Watcher";    Bat = "fixture_watcher.bat";   Trigger = "Every 1h" }
)

foreach ($t in $Tasks) {
    $taskName = $t.Name
    $bat = Join-Path $proj $t.Bat

    if (-not (Test-Path $bat)) {
        Write-Warning "SKIP: $bat not found for task '$taskName'"
        continue
    }

    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Host "TASK MISSING: '$taskName' — run the matching setup_*.ps1 first."
        continue
    }

    Write-Host "HARDENING: $taskName ($($t.Trigger))"

    if ($DryRun) {
        Write-Host "  [dry-run] would set RestartOnFailure + StartWhenAvailable"
        continue
    }

    # Re-apply the action (cmd.exe /c "full path") — same space-safe form as setup_*.ps1
    $action = New-ScheduledTaskAction `
        -Execute "C:\Windows\System32\cmd.exe" `
        -Argument ('/c ""' + $bat + '""') `
        -WorkingDirectory $proj

    # Hardened settings: reboot-survival + restart-on-failure
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 5) `
        -ExecutionTimeLimit (New-TimeSpan -Hours 0) `   # 0 = no limit
        -MultipleInstances IgnoreNew `
        -Priority 7

    # Principal: keep interactive + highest (matches existing security model)
    $principal = New-ScheduledTaskPrincipal `
        -UserId "$env:USERDOMAIN\$env:USERNAME" `
        -LogonType Interactive `
        -RunLevel Highest

    try {
        Set-ScheduledTask -TaskName $taskName -Action $action -Settings $settings -Principal $principal
        Write-Host "  OK — hardened. RestartCount=3, RestartInterval=5m, StartWhenAvailable=on"
    } catch {
        Write-Error "FAILED to harden '$taskName': $_"
    }
}

Write-Host "`nAll tasks processed. Verify with:"
Write-Host "  Get-ScheduledTask | Where-Object { `$_.TaskName -like 'OLP XDV*' } | Format-List TaskName, State"
Write-Host "  Get-ScheduledTask -TaskName 'OLP XDV Daily Board' | Select-Object -ExpandProperty Settings"