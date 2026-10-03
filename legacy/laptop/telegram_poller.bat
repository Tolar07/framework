@echo off
REM ==========================================================================
REM OLP XDV - Telegram command poller daemon (the Architect's way in).
REM
REM Reads commands sent to the bot (/send, /status, /board, /why, /log, ...)
REM and answers them. Runs --loop with LONG-POLLING: the process sits resident
REM and blocks on getUpdates, so a message is answered within seconds, not on
REM a schedule.
REM
REM Normally this is launched HIDDEN by telegram_poller_hidden.vbs via the
REM "OLP XDV Telegram Daemon" task (registered by setup_poller_daemon.ps1 at
REM logon). Running it here manually opens a window you can watch.
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

REM -u keeps the daemon's log lines visible in real time (stdout to a file
REM is block-buffered by default, so messages would hide until the buffer
REM filled).
"%PY%" -u output\telegram_commands.py --loop >> "logs\poller.log" 2>&1
