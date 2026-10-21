@echo off
title Iniciando Bot Automatico...
cd /d "%~dp0"
call venv\Scripts\activate.bat
set NODE_SKIP_PLATFORM_CHECK=1
echo Encendiendo Bot Automatico de forma invisible...
start "" pythonw main.py
exit
