@echo off
REM ==========================================================================
REM OLP XDV - Telegram command poller (the Architect's way in).
REM
REM Reads commands sent to the bot (/send, /status, /board, /why, /log, ...)
REM and answers them. Run this in its own window and leave it open for near-
REM instant response, OR register it as a Windows Task Scheduler task that
REM runs the single-pass form for you:
REM     "%PY%" output\telegram_commands.py
REM (no --loop) as often as you like - each pass is stateless, offset is
REM persisted to memory\telegram_offset.json between passes.
REM
REM Same minimal-role discipline as run_daily.bat: this file only starts
REM Python. All behaviour lives in Python where it is testable.
REM
REM SECURITY: only the whitelisted chat (TELEGRAM_CHAT_ID) is answered;
REM everyone else gets silence, logged. Nothing here can touch capital -
REM config.assert_paper_only() guards the write path underneath.
REM ==========================================================================

cd /d "%~dp0"
if not exist "logs" mkdir "logs"

set "PYTHONIOENCODING=utf-8"
set "PY=C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"

"%PY%" output\telegram_commands.py --loop >> "logs\poller.log" 2>&1
