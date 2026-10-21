@echo off
title Encendido Maestro - Bot Universidad Online
cd /d "%~dp0"

echo [1/4] Limpiando procesos fantasmas atascados...
taskkill /F /IM pythonw.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1

echo [2/4] Verificando dependencias...
pip install flask flask-cors >nul 2>&1

echo [3/4] Encendiendo Motores (Modo Fantasma 100% Invisible)...
start "" pythonw main.py
start "" pythonw vigia_mentorias.py
start "" pythonw dashboard_web.py

echo [4/4] Dando 8 segundos al servidor para arrancar...
timeout /t 8 /nobreak >nul

echo Abriendo Panel Web...
start chrome "http://127.0.0.1:8000" --user-data-dir="%~dp0perfil_chrome"
exit
