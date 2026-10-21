@echo off
chcp 65001 >nul
title Bot Universidad Online - Vigia de Telegram (Mentorias)
color 0D

cd /d "%~dp0"

:: 1. Activar entorno virtual si existe
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

:: 2. Asegurar PYTHONPATH incluyendo raíz y carpeta libs
set "PYTHONPATH=%~dp0;%~dp0libs;%PYTHONPATH%"

:: 3. Detectar ejecutable de Python
set "PY_CMD="
if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0venv\Scripts\python.exe"
) else if exist "C:\Program Files\Python38\python.exe" (
    set "PY_CMD=C:\Program Files\Python38\python.exe"
) else (
    set "PY_CMD=python"
)

echo ======================================================================
echo    BOT UNIVERSIDAD ONLINE - VIGIA DE TELEGRAM (MENTORIAS)
echo ======================================================================
echo Iniciando Lector y Detector de Telegram...
echo.

"%PY_CMD%" vigia_mentorias.py

pause
