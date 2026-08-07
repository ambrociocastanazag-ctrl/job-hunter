@echo off
REM Entry point for the "JobHunter Dashboard" scheduled task (At Logon).
REM Starts the dashboard, which owns the in-process scheduler (automation/scheduler.py)
REM that fires the horarios configured in /schedules.
cd /d "%~dp0.."
call ..\venv\Scripts\activate.bat
python dashboard\app.py >> logs\dashboard.log 2>&1
deactivate
