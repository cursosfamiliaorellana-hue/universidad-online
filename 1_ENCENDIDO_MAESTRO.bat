@echo off
title Encendido Maestro - Bot Universidad Online
cd /d "%~dp0"

set PYTHONW_CMD=pythonw.exe
if exist "venv\Scripts\pythonw.exe" (
    set "PYTHONW_CMD=venv\Scripts\pythonw.exe"
) else if exist "..\venv\Scripts\pythonw.exe" (
    set "PYTHONW_CMD=..\venv\Scripts\pythonw.exe"
)

start "" "%PYTHONW_CMD%" main.py
start "" "%PYTHONW_CMD%" vigia_mentorias.py
start "" "%PYTHONW_CMD%" dashboard_web.py

start "" "http://127.0.0.1:8000"
exit
