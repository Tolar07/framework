@echo off
REM ==========================================================================
REM OLP XDV - MCP watchdog, for Task Scheduler.
REM
REM Runs monitor\mcp_health.py ONCE (one full probe + state log +
REM best-effort Telegram alert on STATE CHANGES only). The monitor is stateless
REM between fires except for logs\mcp_health.json (last-reported states), so
REM every fire is safe to re-run and an issue re-alerts at most once per ~day.
REM
REM Registered (idempotently) by scripts\install_scheduler_tasks.ps1.
REM
REM Every fire appends a line to logs\mcp_watchdog.log, so a missing line
REM means the task did not fire - a different fault from Python crashing.
REM ==========================================================================

cd /d "%~dp0"
if not exist "logs" mkdir "logs"

REM Rotate .bat-redirected logs before writing new entries (10MB/5 backups)
set "PY=C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"
"%PY%" scripts\rotate_logs.py >> "logs\mcp_watchdog.log" 2>&1

echo [%date% %time%] mcp_watchdog.bat invoked >> "logs\mcp_watchdog.log"

set "PYTHONIOENCODING=utf-8"

"%PY%" monitor\mcp_health.py >> "logs\mcp_watchdog.log" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] python exited with %RC% >> "logs\mcp_watchdog.log"
exit /b %RC%