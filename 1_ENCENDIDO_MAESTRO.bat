@echo off
title Encendido Maestro - Bot Universidad Online
cd /d "%~dp0"

echo [1/3] Activando Entorno Virtual...
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
) else (
    echo [AVISO] No se encontro venv\Scripts\activate.bat
)

echo [2/3] Encendiendo Motores Fantasma...
:: Forzamos el uso del pythonw del entorno virtual si existe
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" main.py
    start "" "venv\Scripts\pythonw.exe" vigia_mentorias.py
    start "" "venv\Scripts\pythonw.exe" dashboard_web.py
) else (
    start "" pythonw main.py
    start "" pythonw vigia_mentorias.py
    start "" pythonw dashboard_web.py
)

echo [3/3] Dando 8 segundos a Flask para arrancar...
timeout /t 8 /nobreak >nul

echo Abriendo Panel Web en el perfil de Chrome...
start chrome "http://127.0.0.1:8000" --user-data-dir="%~dp0perfil_chrome"
exit
