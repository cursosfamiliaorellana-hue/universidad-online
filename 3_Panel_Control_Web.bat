@echo off
chcp 65001 >nul
title Bot Universidad Online - Panel de Control Web

cd /d "%~dp0"

:: 1. Activar entorno virtual si existe
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

:: 2. Asegurar PYTHONPATH incluyendo raíz y carpeta libs
set "PYTHONPATH=%~dp0;%~dp0libs;%PYTHONPATH%"

:: 3. Detectar ejecutable de PythonW (ejecución en segundo plano sin ventana negra)
set "PYW_CMD="
if exist "%~dp0venv\Scripts\pythonw.exe" (
    set "PYW_CMD=%~dp0venv\Scripts\pythonw.exe"
) else if exist "C:\Program Files\Python38\pythonw.exe" (
    set "PYW_CMD=C:\Program Files\Python38\pythonw.exe"
) else (
    where pythonw >nul 2>&1 && set "PYW_CMD=pythonw"
)

if not defined PYW_CMD (
    if exist "%~dp0venv\Scripts\python.exe" (
        set "PYW_CMD=%~dp0venv\Scripts\python.exe"
    ) else if exist "C:\Program Files\Python38\python.exe" (
        set "PYW_CMD=C:\Program Files\Python38\python.exe"
    ) else (
        set "PYW_CMD=python"
    )
)

echo ======================================================================
echo    BOT UNIVERSIDAD ONLINE - PANEL DE CONTROL WEB INTERACTIVO
echo    Iniciando servidor local en segundo plano (http://127.0.0.1:8000)...
echo ======================================================================
echo.

start "" "%PYW_CMD%" dashboard_web.py

echo [OK] Panel de control iniciado en segundo plano sin bloquear tu consola.
echo [OK] Abriendo navegador predeterminado en http://127.0.0.1:8000 ...
timeout /t 2 >nul
exit
