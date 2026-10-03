<#
.SYNOPSIS
    Multi-channel alert dispatcher (PowerShell-independent version).

.DESCRIPTION
    Reads .env directly (no Python dependency) and fans out an alert to:
      - Telegram (Bot API)
      - Email (SMTP)
      - Webhook (generic JSON POST)

    Deduplicates by (level, title, tags) within a 1-hour window by writing
    to logs/alert_dedup.json.

    This is the PowerShell sibling of monitor/alert_dispatcher.py — used by
    .bat launchers that need independence from the Python install (same
    reasoning as alert_failure.ps1).

.PARAMETER Level
    "info" | "warn" | "error" | "critical"

.PARAMETER Title
    Short alert title (used for deduplication)

.PARAMETER Body
    Full alert message body

.PARAMETER Tags
    Comma-separated tags (e.g. "dr,restore-test-failed")

.EXAMPLE
    .\monitor\alert_dispatcher.ps1 -Level "critical" -Title "Quota exhausted" -Body "1 call left" -Tags "quota,odds"
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("info", "warn", "error", "critical")]
    [string]$Level,

    [Parameter(Mandatory = $true)]
    [string]$Title,

    [Parameter(Mandatory = $true)]
    [string]$Body,

    [string]$Tags = "",

    [string]$EnvPath = ""
)

$ErrorActionPreference = "SilentlyContinue"

# Resolve repo root (parent of the monitor/ directory)
if (-not $EnvPath) {
    $EnvPath = Join-Path (Split-Path -Parent $PSScriptRoot) ".env"
}
$DedupFile = Join-Path (Split-Path -Parent $PSScriptRoot) "logs\alert_dedup.json"
$WindowSeconds = 3600

# --- Parse .env (regex, no Python dependency) ---
$envVars = @{}
if (Test-Path $EnvPath) {
    Get-Content $EnvPath | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $k, $v = $line.Split("=", 2)
            $envVars[$k.Trim()] = $v.Trim()
        }
    }
}

function Send-Telegram($token, $chatId, $text) {
    if (-not $token -or -not $chatId) { return $false, "missing token/chat_id" }
    try {
        $url = "https://api.telegram.org/bot$token/sendMessage"
        $body = @{ chat_id = $chatId; text = $text } | ConvertTo-Json -Compress
        $resp = Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json" -Body $body -TimeoutSec 30
        return $true, "telegram ok"
    } catch {
        return $false, "telegram error: $_"
    }
}

function Send-Email($host_, $port, $user, $pass, $to, $subject, $emailBody) {
    if (-not ($host_ -and $port -and $user -and $pass -and $to)) { return $false, "missing SMTP config" }
    try {
        $securePass = ConvertTo-SecureString $pass -AsPlainText -Force
        $cred = New-Object System.Management.Automation.PSCredential($user, $securePass)
        Send-MailMessage -SmtpServer $host_ -Port $port -UseSsl -Credential $cred `
            -From $user -To $to -Subject $subject -Body $emailBody -TimeoutSec 30
        return $true, "email ok"
    } catch {
        return $false, "email error: $_"
    }
}

function Send-Webhook($url, $payloadJson) {
    if (-not $url) { return $false, "missing webhook url" }
    try {
        Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json" -Body $payloadJson -TimeoutSec 30
        return $true, "webhook ok"
    } catch {
        return $false, "webhook error: $_"
    }
}

# --- Deduplication ---
function Get-DedupState {
    if (Test-Path $DedupFile) {
        try { return (Get-Content $DedupFile | ConvertFrom-Json -AsHashtable) } catch { return @{} }
    }
    return @{}
}

function Save-DedupState($state) {
    $parent = Split-Path -Parent $DedupFile
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    $state | ConvertTo-Json | Set-Content $DedupFile
}

$tagList = @($Tags -split "," | Where-Object { $_ } | ForEach-Object { $_.Trim() })
$key = "$Level|$Title|$(($tagList | Sort-Object) -join ',')"

$dedup = Get-DedupState
$shouldAlert = $true
if ($dedup.ContainsKey($key)) {
    $elapsed = [int]((Get-Date) - [datetime]::Parse($dedup[$key].ts, [System.Globalization.CultureInfo]::InvariantCulture)).TotalSeconds
    if ($elapsed -lt $WindowSeconds) { $shouldAlert = $false }
}

if (-not $shouldAlert) {
    Write-Host "SUPPRESSED: alert within window ($key)"
    exit 0
}

# --- Dispatch ---
$results = @{}

$ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$tgText = "[$($Level.ToUpper())] $Title`n`n$Body`n`n$(('=' * 34))`nOLP XDV — Honest edge: not a demonstrated edge · Capital: Architect only."

$token = $envVars["TELEGRAM_BOT_TOKEN"]
$chatId = $envVars["TELEGRAM_CHAT_ID"]
$results["telegram"] = Send-Telegram $token $chatId $tgText

$subject = "[OLP XDV $($Level.ToUpper())] $Title"
$emailBody = "$Body`n`nTags: $(if ($tagList) { $tagList -join ', ' } else { 'none' })`nTimestamp: $ts"
$results["email"] = Send-Email $envVars["ALERT_SMTP_HOST"] $envVars["ALERT_SMTP_PORT"] `
    $envVars["ALERT_SMTP_USER"] $envVars["ALERT_SMTP_PASS"] $envVars["ALERT_EMAIL_TO"] $subject $emailBody

$payload = @{ timestamp = $ts; level = $Level; title = $Title; body = $Body; tags = $tagList } | ConvertTo-Json -Compress
$results["webhook"] = Send-Webhook $envVars["ALERT_WEBHOOK_URL"] $payload

# --- Record alerted ---
if ($results.Values | Where-Object { $_.Item1 }) {
    $dedup[$key] = @{ ts = (Get-Date).ToString("o"); level = $Level; title = $Title; tags = $tagList }
    Save-DedupState $dedup
}

# --- Report ---
foreach ($ch in $results.Keys) {
    $ok, $note = $results[$ch]
    Write-Host "$ch`: $(if ($ok) { 'OK' } else { 'FAIL' }) — $note"
}

exit 0