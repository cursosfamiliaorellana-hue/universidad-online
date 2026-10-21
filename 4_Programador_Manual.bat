@echo off
chcp 1252 >nul
title Bot Universidad Online - Programador Manual
color 0E

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

"%PY_CMD%" programador_manual.py

pause
