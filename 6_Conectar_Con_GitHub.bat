@echo off
chcp 1252 >nul
title Bot Universidad Online - Conectar con GitHub Pages y Disaster Recovery
color 0B

cd /d "%~dp0"

:: 1. Activar entorno virtual si existe
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

:: 2. Asegurar PYTHONPATH incluyendo raíz y carpeta libs
set "PYTHONPATH=%~dp0;%~dp0libs;%PYTHONPATH%"

:: 3. Configurar safe.directory en Git
if exist "%~dp0git\cmd\git.exe" (
    "%~dp0git\cmd\git.exe" config --global --add safe.directory "*" >nul 2>&1
)

:: 4. Detectar ejecutable de Python
set "PY_CMD="
if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0venv\Scripts\python.exe"
) else if exist "C:\Program Files\Python38\python.exe" (
    set "PY_CMD=C:\Program Files\Python38\python.exe"
) else (
    set "PY_CMD=python"
)

echo ======================================================================
echo    BOT UNIVERSIDAD ONLINE - ASISTENTE DE CONEXION CON GITHUB
echo ======================================================================
echo.

"%PY_CMD%" setup_github.py

pause
