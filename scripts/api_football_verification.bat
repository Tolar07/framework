@echo off
REM api_football_verification.bat — Task Scheduler wrapper for API-Football verification
REM
REM Usage: api_football_verification.bat [date] [format] [quiet]
REM   date    - YYYY-MM-DD (defaults to yesterday)
REM   format  - json or text (defaults to text)
REM   quiet   - "quiet" to suppress progress output
REM
REM Task Scheduler Registration:
REM   powershell -ExecutionPolicy Bypass -File setup_verification_task.ps1
REM
REM Environment:
REM   API_FOOTBALL_KEY must be set in .env or system environment

cd /d "%~dp0.."

REM Load .env if present
if exist .env (
    for /f "usebackq delims=" %%a in (`.env 2^>nul`) do set "%%a"
)

REM Default to yesterday if no date provided
set TARGET_DATE=%1
if "%TARGET_DATE%"=="" (
    for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
    set TARGET_DATE=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%
    REM Calculate yesterday - using PowerShell for date math
    for /f %%I in ('powershell -NoProfile -Command "(Get-Date).AddDays(-1).ToString('yyyy-MM-dd')"') do set TARGET_DATE=%%I
)

set FORMAT=%2
if "%FORMAT%"=="" set FORMAT=text

set QUIET=%3
if "%QUIET%"=="" set QUIET=

REM Set Python path
set PYTHON=python
if exist .venv\Scripts\python.exe set PYTHON=.venv\Scripts\python.exe

REM Log directory
set LOG_DIR=logs\api_football_verification
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Log file with date
set LOGFILE=%LOG_DIR%\verification_%TARGET_DATE%.log

echo [%date% %time%] Starting API-Football verification for %TARGET_DATE% >> "%LOGFILE%"
echo [%date% %time%] Format: %FORMAT% Quiet: %QUIET% >> "%LOGFILE%"

REM Run verification
if "%QUIET%"=="quiet" (
    %PYTHON% scripts\api_football_verification.py --date %TARGET_DATE% --format %FORMAT% --quiet >> "%LOGFILE%" 2>&1
) else (
    %PYTHON% scripts\api_football_verification.py --date %TARGET_DATE% --format %FORMAT% >> "%LOGFILE%" 2>&1
)

set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE%==0 (
    echo [%date% %time%] Verification completed successfully (exit code %EXIT_CODE%) >> "%LOGFILE%"
) else (
    echo [%date% %time%] Verification FAILED (exit code %EXIT_CODE%) >> "%LOGFILE%"
)

exit /b %EXIT_CODE%