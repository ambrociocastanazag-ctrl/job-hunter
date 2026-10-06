@echo off
REM Lanzador de Job Hunter: lo abre el acceso directo del escritorio que crea
REM install.ps1. Levanta el dashboard en esta ventana y abre el navegador;
REM cerrar la ventana apaga el servidor (y una busqueda en curso, si la hay).
REM   JobHunter.bat              -> abre el navegador
REM   JobHunter.bat /background  -> sin navegador (inicio con Windows)
title Job Hunter
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=..\venv\Scripts\python.exe"
if not exist "%PY%" (
    echo No se encontro el entorno de Python de Job Hunter.
    echo Vuelve a correr el comando de instalacion de la guia.
    pause
    exit /b 1
)

set "BROWSER=--open-browser"
if /i "%~1"=="/background" set "BROWSER="

echo.
echo   Job Hunter esta corriendo. Cierra esta ventana para apagarlo.
echo.
"%PY%" dashboard\app.py %BROWSER%
if errorlevel 1 pause
