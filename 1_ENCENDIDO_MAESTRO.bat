@echo off
title Encendido Maestro - Bot Universidad Online
cd /d "%~dp0"

echo [1/3] Activando Entorno Virtual...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "env\Scripts\activate.bat" (
    call env\Scripts\activate.bat
)

echo [2/3] Encendiendo Motores en Modo Fantasma...
start "" pythonw main.py
start "" pythonw vigia_mentorias.py
start "" pythonw dashboard_web.py

echo [3/3] Esperando a que el Panel Web inicie...
timeout /t 4 /nobreak >nul

echo Abriendo Panel Web en el perfil del Bot...
start chrome "http://127.0.0.1:8000" --user-data-dir="%~dp0perfil_chrome"

exit
