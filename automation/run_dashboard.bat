@echo off
REM Entry point for the "JobHunter Dashboard" scheduled task (At Logon).
REM Opens the same window as the desktop shortcut, minimized and without the
REM browser. The dashboard owns the in-process scheduler (automation/scheduler.py)
REM that fires the horarios configured in /schedules; closing the window stops it.
start "Job Hunter" /min "%~dp0..\JobHunter.bat" /background
