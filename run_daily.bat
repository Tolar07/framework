@echo off
REM ==========================================================================
REM OLP XDV - laptop nightly loop: RETIRED 2026-10-03.
REM
REM The laptop and cloud lines were merged into one repo with main's code
REM winning (docs/LINEAGE_MERGE_2026-10-03.md). The daily board, CLV capture
REM and the Survivor lineage now run only in GitHub Actions
REM (.github/workflows/daily.yml, 05:47 and 20:47 UTC).
REM
REM This launcher stays so the Windows Task Scheduler entry exits cleanly and
REM leaves a dated line in logs\launcher.log instead of calling run_daily.py
REM with the laptop-only flags (--agreement-band, --date) that main's
REM run_daily.py rejects, which would fail and alert every night. It does NOT
REM run the pipeline and sends nothing. Disable the scheduled task when
REM convenient; the laptop line's launcher is at 81ef177:run_daily.bat.
REM ==========================================================================

cd /d "%~dp0"
if not exist "logs" mkdir "logs"

echo [%date% %time%] launcher invoked - laptop loop retired 2026-10-03; the board runs in GitHub Actions (daily.yml). Nothing run. >> "logs\launcher.log"

exit /b 0
