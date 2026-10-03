@echo off
REM ==========================================================================
REM OLP XDV - Fixture Watcher, launched by Windows Task Scheduler.
REM
REM Runs fixture extraction hourly to update fixture statuses (kicked off /
REM upcoming) and refresh Stage A artifacts.
REM ==========================================================================

cd /d "%~dp0"
if not exist "logs" mkdir "logs"

set "PY=C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"
"%PY%" scripts\rotate_logs.py >> "logs\fixture_watcher.log" 2>&1

echo [%date% %time%] fixture_watcher launcher invoked >> "logs\fixture_watcher.log"

set "PYTHONIOENCODING=utf-8"

"%PY%" -m pipeline.fixture_extraction --filter-upcoming >> "logs\fixture_watcher.log" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] fixture_watcher python exited with %RC% >> "logs\fixture_watcher.log"

if not "%RC%"=="0" (
  echo [%date% %time%] FIXTURE WATCHER RUN FAILED - alerting >> "logs\fixture_watcher.log"
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0alert_failure.ps1" -ExitCode %RC% -Label "the Fixture Watcher" -Log "fixture_watcher.log" >> "logs\fixture_watcher.log" 2>&1
)

exit /b %RC%