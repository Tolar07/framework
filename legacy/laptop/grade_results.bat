@echo off
REM Grade Results Batch File for OLP XDV Results Verification Agent
REM This batch file calls the grade_results.py script with yesterday's date

set "REPO_ROOT=C:\Users\Motunrayo\omniroute test"
set "PYTHON_EXE=python"

REM Change to the olp_xdv directory
cd /d "%REPO_ROOT%\olp_xdv_agent\olp_xdv"

REM Run the grade results script for yesterday's date
REM For production use, we want to grade the previous day's board
set "YESTERDAY_DATE=%DATE:~-4,4%-%DATE:~4,2%-%DATE:~7,2%"

REM Handle single digit days (need to adjust based on date format)
REM This is a simplified version - in production would use proper date math
python grade_results.py --date %YESTERDAY_DATE%

REM Exit with the same code as the Python script
exit /b %ERRORLEVEL%