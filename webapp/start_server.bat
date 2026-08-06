@echo off
REM OLP XDV dashboard launcher — double-click to start, opens the browser.
REM Binds 0.0.0.0 so a phone on the same Wi-Fi can open http://<PC-IP>:8088
REM (find the PC IP with `ipconfig`). The dashboard is read-only.
cd /d "%~dp0.."
start "" "http://localhost:8088/board/%date:~10,4%-%date:~4,2%-%date:~7,2%"
"py" webapp\server.py --host 0.0.0.0 --port 8088
