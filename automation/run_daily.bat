@echo off
REM Fallback manual/CLI entry point. La automatizacion principal ahora vive
REM en el dashboard (automation/scheduler.py) via la tarea "JobHunter Dashboard".
cd /d "%~dp0.."
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=..\venv\Scripts\python.exe"
if not exist logs mkdir logs
"%PY%" main.py --mode daily >> logs\scheduler.log 2>&1
