@echo off
cd /d "C:\Users\WINDOWS\Desktop\Proyecto Jobspy\job_hunter"
call ..\venv\Scripts\activate.bat
python main.py --mode daily >> logs\scheduler.log 2>&1
deactivate
