@echo off
REM ==========================================================================
REM OLP XDV - dead-man's-switch for the 07:00 daily run, for Task Scheduler.
REM
REM Runs monitor\dead_mans_switch.py ONCE (~08:00, after the 07:00 slot).
REM Fires a DISTINCT Telegram alert if today's run did not complete AND deliver.
REM This is NOT the health monitor — it answers ONLY: "Did the 07:00 job run?"
REM ==========================================================================

cd /d "%~dp0"
if not exist "logs" mkdir "logs"
echo [%date% %time%] dead_mans_switch.bat invoked >> "logs\dead_mans_switch.log"

set "PYTHONIOENCODING=utf-8"
set "PY=C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"

"%PY%" monitor\dead_mans_switch.py >> "logs\dead_mans_switch.log" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] python exited with %RC% >> "logs\dead_mans_switch.log"
exit /b %RC%