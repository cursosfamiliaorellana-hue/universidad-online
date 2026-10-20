@echo off
chcp 1252 >nul
title Bot Universidad Online - Gestor de Re-grabacion y Repeticiones
color 0B

cd /d "%~dp0"
set "PYTHONPATH=%~dp0libs"

"C:\Program Files\Python38\python.exe" gestor_regrabacion.py

pause