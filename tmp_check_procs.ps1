Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match 'telegram|poller|daily|run_daily'
} | Select-Object ProcessId, Name, @{N='CmdLine';E={$_.CommandLine.Substring(0, [Math]::Min(120, $_.CommandLine.Length))}} | Format-Table -AutoSize -Wrap
