@echo off
REM ==========================================================================
REM OLP XDV - 03:00 daily FlashScore fixtures scrape, launched by Windows Task
REM Scheduler.
REM
REM Captures ALL whitelisted-league fixtures (upcoming rounds = 2-day+ advance
REM data) into data/live_odds/flashscore_odds_<timestamp>.jsonl. Same minimal
REM launcher pattern as run_daily.bat: do as little as possible here, log
REM unconditionally BEFORE invoking Python so a scheduled miss is visible.
REM
REM Space-safe: the .bat lives in "omniroute test" (a path with a space), so the
REM task must invoke cmd.exe and pass the full path as ONE double-quoted arg.
REM ==========================================================================

cd /d "%~dp0"
if not exist "logs" mkdir "logs"

set "PY=C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"

echo [%date% %time%] flashscore scrape launcher invoked >> "logs\scrape_flashscore.log"

set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"

"%PY%" scripts\scrape_live_odds_v3.py >> "logs\scrape_flashscore.log" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] python exited with %RC% >> "logs\scrape_flashscore.log"

exit /b %RC%
