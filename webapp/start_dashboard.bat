@echo off
REM ==========================================================================
REM OLP XDV - web dashboard server launcher (hidden, for Startup auto-start).
REM
REM Same minimal-role discipline as telegram_poller.bat: this file only starts
REM Python. All behaviour lives in Python where it is testable.
REM
REM Logs to logs\web_server.log so a boot-time failure leaves evidence.
REM ==========================================================================

cd /d "%~dp0.."
if not exist "logs" mkdir "logs"

set "PYTHONIOENCODING=utf-8"
set "PY=C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"

REM -u keeps server log lines visible in real time (stdout to a file is
REM block-buffered by default).
"%PY%" -u webapp\server.py --host 0.0.0.0 --port 8088 >> "logs\web_server.log" 2>&1
