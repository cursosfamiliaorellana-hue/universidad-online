@echo off
title Encendido Maestro - Bot Universidad Online
cd /d "%~dp0"

echo [1/4] Limpiando procesos fantasmas (Zombies) atascados...
taskkill /F /IM pythonw.exe >nul 2>&1

echo [2/4] Verificando dependencias en Python Global...
pip install flask flask-cors >nul 2>&1

echo [3/4] Encendiendo Motores (Web en modo visible para depuracion)...
start "" pythonw main.py
start "" pythonw vigia_mentorias.py
start "" cmd /k python dashboard_web.py

echo [4/4] Dando 8 segundos al servidor para arrancar...
timeout /t 8 /nobreak >nul

echo Abriendo Panel Web en el perfil de Chrome...
start chrome "http://127.0.0.1:8000" --user-data-dir="%~dp0perfil_chrome"
exit
