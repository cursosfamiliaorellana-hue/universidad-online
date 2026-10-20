@echo off
chcp 1252 >nul
title Bot Universidad Online - Panel de Control Web
color 0B

cd /d "%~dp0"
set "PYTHONPATH=%~dp0libs"

echo ======================================================================
echo    BOT UNIVERSIDAD ONLINE - PANEL DE CONTROL WEB INTERACTIVO
echo    Iniciando servidor local en http://127.0.0.1:8000 ...
echo ======================================================================
echo.

if exist "C:\Program Files\Python38\python.exe" (
    "C:\Program Files\Python38\python.exe" dashboard_web.py
) else (
    python dashboard_web.py
)

pause
