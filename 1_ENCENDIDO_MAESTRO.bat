@echo off
title Encendido Maestro - Bot Universidad Online
cd /d "%~dp0"

echo [1/3] Detectando entorno virtual y encendiendo motores fantasma...
set "VENV_PATH="
if exist "venv\Scripts\pythonw.exe" set "VENV_PATH=venv"
if exist ".venv\Scripts\pythonw.exe" set "VENV_PATH=.venv"
if exist "env\Scripts\pythonw.exe" set "VENV_PATH=env"

if defined VENV_PATH (
    start "" "%~dp0%VENV_PATH%\Scripts\pythonw.exe" main.py
    start "" "%~dp0%VENV_PATH%\Scripts\pythonw.exe" vigia_mentorias.py
    start "" "%~dp0%VENV_PATH%\Scripts\pythonw.exe" dashboard_web.py
) else (
    echo [AVISO] No se encontro VENV, usando Python global...
    start "" pythonw main.py
    start "" pythonw vigia_mentorias.py
    start "" pythonw dashboard_web.py
)

echo [2/3] Dando tiempo a la laptop para iniciar el servidor web...
timeout /t 8 /nobreak >nul

echo [3/3] Abriendo Panel Web en el perfil de Chrome...
start chrome "http://127.0.0.1:8000" --user-data-dir="%~dp0perfil_chrome"
exit
