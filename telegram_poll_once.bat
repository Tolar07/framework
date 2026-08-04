@echo off
REM ==========================================================================
REM OLP XDV - single-pass Telegram command poll, for Task Scheduler.
REM
REM Runs output\telegram_commands.py ONCE (no --loop). Each scheduled fire
REM handles whatever messages have arrived since the last one; the getUpdates
REM offset is persisted in memory\telegram_offset.json between fires, so each
REM pass is stateless and safe to re-run.
REM
REM Registered (idempotently) by setup_poller_task.ps1. Evidence: every fire
REM appends a line to logs\poller.log, so a missing line means the task did
REM not fire - a different fault from Python running and crashing.
REM ==========================================================================

cd /d "%~dp0"
if not exist "logs" mkdir "logs"

set "PYTHONIOENCODING=utf-8"
set "PY=C:\Users\Motunrayo\AppData\Local\Programs\Python\Python312\python.exe"

"%PY%" output\telegram_commands.py >> "logs\poller.log" 2>&1
