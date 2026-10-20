@echo off
chcp 1252 >nul
title Bot Universidad Online - Conectar con GitHub Pages
color 0B

cd /d "%~dp0"
set "PYTHONPATH=%~dp0libs"

echo ======================================================================
echo    BOT UNIVERSIDAD ONLINE - CONEXION CON GITHUB PAGES
echo ======================================================================
echo.

if exist "%~dp0git\cmd\git.exe" (
    "%~dp0git\cmd\git.exe" config --global --add safe.directory "*" >nul 2>&1
)

if exist "C:\Program Files\Python38\python.exe" (
    "C:\Program Files\Python38\python.exe" configurar_github.py
) else (
    python configurar_github.py
)

pause
