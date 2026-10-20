@echo off
chcp 1252 >nul
title Bot Universidad Online - Vigia de Telegram (Mentorias)
color 0D

cd /d "%~dp0"
set "PYTHONPATH=%~dp0libs"

echo Iniciando Lector de Telegram en segundo plano...
"C:\Program Files\Python38\python.exe" vigia_mentorias.py

pause