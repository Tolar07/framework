@echo off
REM ==========================================================================
REM OLP XDV - web tier supervisor (wrapped by NSSM as "OLP XDV Web").
REM
REM Runs the Python dashboard + Caddy in the FOREGROUND (so NSSM can see the
REM process and restart it on crash). Inner loop restarts either child if it
REM exits unexpectedly; NSSM is the outer safety net (restart-on-failure).
REM
REM NSSM must point at THIS file, not start_dashboard_tls.bat (which uses
REM `start` and exits immediately — unsuitable for a service).
REM ==========================================================================

cd /d "%~dp0.."
if not exist "logs" mkdir "logs"

set "PY=C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"

set "PYTHONIOENCODING=utf-8"

:loop
echo [%date% %time%] web tier starting...
"%PY%" scripts\rotate_logs.py >> "logs\web_server.log" 2>&1

REM Launch Python dashboard on localhost:8088 (internal; Caddy proxies :443).
start "OLP XDV Python" /b cmd /c ""%PY%" -u webapp\server.py --host 127.0.0.1 --port 8088 >> "logs\web_server.log" 2>&1"

REM Give Python a moment to bind before Caddy starts.
timeout /t 3 /nobreak >nul

REM Launch Caddy (foreground — blocks until it exits; loop restarts on crash).
caddy run --config Caddyfile >> "logs\web_server.log" 2>&1

echo [%date% %time%] web tier exited (code %errorlevel%) -- restarting in 5s...
timeout /t 5 /nobreak >nul
goto loop
