@echo off
REM Fallback manual/CLI entry point. La automatizacion principal ahora vive
REM en el dashboard (automation/scheduler.py) via la tarea "JobHunter Dashboard".
cd /d "%~dp0.."
call ..\venv\Scripts\activate.bat
python main.py --mode daily >> logs\scheduler.log 2>&1
deactivate
