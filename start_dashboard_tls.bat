@echo off
title OLP XDV Dashboard (TLS via Caddy)
cd /d "%~dp0"

REM ============================================================
REM  OLP XDV Dashboard with automatic HTTPS via Caddy
REM ============================================================
REM
REM  This script starts:
REM    1. The Python dashboard server on localhost:8088 (internal only)
REM    2. Caddy reverse proxy on :443 with automatic Let's Encrypt HTTPS
REM
REM  Prerequisites:
REM    - Install Caddy: https://caddyserver.com/docs/install
REM      (Windows: scoop install caddy  OR  choco install caddy)
REM    - For production: a real domain pointing to this machine
REM    - For LAN testing: uses self-signed certs (browser warning expected)
REM
REM  Access:
REM    - Local:     https://localhost      (accept self-signed warning)
REM    - LAN:       https://<your-LAN-IP>  (accept self-signed warning)
REM    - Production: https://yourdomain.com (valid Let's Encrypt cert)
REM
REM  To stop: Close this window (Ctrl+C stops both processes)
REM ============================================================

echo ============================================================
echo  OLP XDV Dashboard - TLS via Caddy
echo ============================================================
echo.

REM Check for Caddy
where caddy >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Caddy not found in PATH.
    echo Install it first: https://caddyserver.com/docs/install
    echo   scoop install caddy
    echo   OR
    echo   choco install caddy
    echo.
    pause
    exit /b 1
)

REM Absolute Python path
set "PY=C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"

echo [1/2] Starting Python dashboard on http://localhost:8088 (internal)...
start "OLP XDV Python Server" /min cmd /k ""%PY%" webapp\server.py --host 127.0.0.1 --port 8088"

REM Give Python server time to bind
timeout /t 3 /nobreak >nul

echo [2/2] Starting Caddy reverse proxy on :443 (HTTPS)...
echo.
echo  Access dashboard at:
echo    Local:  https://localhost      (accept browser cert warning)
echo    LAN:    https://<your-LAN-IP>  (accept browser cert warning)
echo.
echo  For PRODUCTION with a real domain:
echo    1. Edit Caddyfile: replace :443 block with your domain
echo    2. Run: caddy run --config Caddyfile
echo.
echo  Press Ctrl+C to stop both servers.
echo.

REM Start Caddy in foreground so Ctrl+C stops everything
caddy run --config Caddyfile