@echo off
title OLP XDV Dashboard
cd /d "%~dp0.."

REM Absolute Python path - the same pattern run_daily.bat uses (proven via the
REM daily scheduled job). Fall back to the `py` launcher if it ever moves.
set "PY=C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"

echo ============================================================
echo  OLP XDV dashboard - starting server (read-only)
echo ============================================================
echo.
echo  The server opens in a MINIMIZED window and keeps running.
echo  Leave it running; close that window to stop the server.
echo.
echo  On this PC:   http://localhost:8088
echo  On your phone (same Wi-Fi): run ipconfig, then open
echo                 http://<your-PC-IPv4>:8088
echo.
REM Start the server FIRST in its own window, give it a moment to bind,
REM THEN open the browser. Opening "/" makes the server redirect to
REM today's board - no fragile %date% parsing.
start "OLP XDV server" /min cmd /k ""%PY%" webapp\server.py --host 0.0.0.0 --port 8088"
timeout /t 3 /nobreak >nul
start "" "http://localhost:8088/"
echo  Browser opened. If it says failed-to-connect, wait 2s and refresh.
timeout /t 5 >nul
