@echo off
REM ==========================================================================
REM OLP XDV - 07:00 daily run, launched by Windows Task Scheduler.
REM
REM This file does as little as possible ON PURPOSE. An earlier version parsed
REM .env with a cmd for-loop and built timestamps; when any of that failed the
REM script aborted BEFORE writing a log, so a scheduled run left no evidence
REM while Task Scheduler still reported success. Everything except "run
REM Python" now lives in Python, where it is testable.
REM
REM The first echo is unconditional and comes before all else: if launcher.log
REM has no new line after a trigger, the batch never ran - a different fault
REM from Python running and crashing.
REM ==========================================================================

cd /d "%~dp0"
if not exist "logs" mkdir "logs"

REM Rotate .bat-redirected logs before writing new entries (10MB/5 backups)
set "PY=C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"
"%PY%" scripts\rotate_logs.py >> "logs\launcher.log" 2>&1

echo [%date% %time%] launcher invoked >> "logs\launcher.log"

set "PYTHONIOENCODING=utf-8"

REM Gambler move #2 (2026-08-14): the agreement gate keeps the daily paper run
REM inside the model's calibrated zone — only bet markets where model and book
REM agree within 0.04 probability. This is the Phase-2 experiment we are
REM backfilling; it MUST be on for the scheduled run or the CLV ledger diverges
REM from the experiment we are measuring.
"%PY%" run_daily.py --agreement-band 0.04 >> "logs\launcher.log" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] python exited with %RC% >> "logs\launcher.log"

if not "%RC%"=="0" (
  echo [%date% %time%] RUN FAILED - alerting >> "logs\launcher.log"
  REM The alert deliberately does NOT use %PY%. When the Python path itself is
  REM what broke, an alert that needs Python cannot fire - the notifier would
  REM share a failure mode with the thing it is monitoring. PowerShell ships
  REM with Windows and is independent of the Python install.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0alert_failure.ps1" -ExitCode %RC% >> "logs\launcher.log" 2>&1
)

exit /b %RC%
