param(
    [int]$ExitCode = 1,
    [string]$Label = "the 07:00 run",
    [string]$Log = "launcher.log"
)

# Delegate to multi-channel alert dispatcher (Telegram + email + webhook)
# Reads .env directly so it needs nothing from the Python environment that just failed.
$ErrorActionPreference = "SilentlyContinue"
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
$dispatcher = Join-Path $proj "monitor\alert_dispatcher.ps1"

if (Test-Path $dispatcher) {
    & $dispatcher -Level "error" -Title "OLP XDV: $Label FAILED (exit $ExitCode)" `
        -Body "This is a SYSTEM FAILURE, not a quiet slate with no picks.`nLog: $proj\logs\$Log" `
        -Tags "failure,$($Log.Replace('.log',''))" -EnvPath "$proj\.env"
} else {
    # Fallback: inline Telegram-only (original behavior)
    $envFile = Join-Path $proj ".env"
    if (-not (Test-Path $envFile)) { Write-Output "no .env - cannot alert"; exit 1 }

    $cfg = @{}
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $k, $v = $line -split '=', 2
        $cfg[$k.Trim()] = $v.Trim().Trim('"').Trim("'")
    }
    $token = $cfg['TELEGRAM_BOT_TOKEN']; $chat = $cfg['TELEGRAM_CHAT_ID']
    if (-not $token -or -not $chat) { Write-Output "no telegram creds - cannot alert"; exit 1 }

    $msg = "OLP XDV: $Label FAILED (exit $ExitCode).`n`n" +
           "This is a SYSTEM FAILURE, not a quiet slate with no picks.`n" +
           "Log: $proj\logs\$Log"
    try {
        Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot$token/sendMessage" `
            -Body @{ chat_id = $chat; text = $msg } -TimeoutSec 30 | Out-Null
        Write-Output "failure alert delivered"
    } catch {
        Write-Output "failure alert could not be delivered: $_"
    }
}
