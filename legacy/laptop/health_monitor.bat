@echo off
REM ==========================================================================
REM OLP XDV - health monitor, for Task Scheduler.
REM
REM Runs monitor\health_monitor.py ONCE (one full check + heal + best-effort
REM Telegram alert on STATE CHANGES only). The monitor is stateless between
REM fires except for logs\health_state.json (last-reported states), so every
REM fire is safe to re-run and an issue re-alerts at most once per ~day.
REM
REM Registered (idempotently) by setup_health_monitor_task.ps1. Evidence:
REM every fire appends a line to logs\health_monitor.log, so a missing line
REM means the task did not fire - a different fault from Python crashing.
REM ==========================================================================

cd /d "%~dp0"
if not exist "logs" mkdir "logs"

REM Rotate .bat-redirected logs before writing new entries (10MB/5 backups)
set "PY=C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"
"%PY%" scripts\rotate_logs.py >> "logs\health_monitor.log" 2>&1

echo [%date% %time%] health_monitor.bat invoked >> "logs\health_monitor.log"

set "PYTHONIOENCODING=utf-8"

"%PY%" monitor\health_monitor.py >> "logs\health_monitor.log" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] python exited with %RC% >> "logs\health_monitor.log"
exit /b %RC%
