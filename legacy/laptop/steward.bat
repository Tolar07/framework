@echo off
REM ==========================================================================
REM OLP XDV - Data Steward, launched by Windows Task Scheduler.
REM
REM One-shot "fetch everything the board needs" pass, registered at 06:00
REM (pre-board) and 15:00 (afternoon refresh). The 07:00 board then always
REM reads fresh data.
REM
REM Same minimal pattern as run_daily.bat ON PURPOSE: everything except "run
REM Python" lives in Python where it is testable. The first echo is
REM unconditional and comes before all else - if steward.log has no new line
REM after a trigger, the batch never ran, a different fault from Python
REM starting and crashing.
REM ==========================================================================

cd /d "%~dp0"
if not exist "logs" mkdir "logs"

REM Rotate .bat-redirected logs before writing new entries (10MB/5 backups)
set "PY=C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"
"%PY%" scripts\rotate_logs.py >> "logs\steward.log" 2>&1

echo [%date% %time%] steward launcher invoked >> "logs\steward.log"

set "PYTHONIOENCODING=utf-8"

"%PY%" steward\run_steward.py >> "logs\steward.log" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] steward python exited with %RC% >> "logs\steward.log"

if not "%RC%"=="0" (
  echo [%date% %time%] STEWARD RUN FAILED - alerting >> "logs\steward.log"
  REM Same alert as run_daily: PowerShell ships with Windows and is
  REM independent of the Python install, so it fires even when the Python
  REM path itself is what broke.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0alert_failure.ps1" -ExitCode %RC% -Label "the Data Steward" -Log "steward.log" >> "logs\steward.log" 2>&1
)

exit /b %RC%
