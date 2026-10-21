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

:: 3. Detectar ejecutable de Python para comandos de consola
set "PY_CMD="
if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0venv\Scripts\python.exe"
) else if exist "C:\Program Files\Python38\python.exe" (
    set "PY_CMD=C:\Program Files\Python38\python.exe"
) else (
    set "PY_CMD=python"
)

:: 4. Detectar ejecutable de PythonW (segundo plano sin ventana negra)
set "PYW_CMD="
if exist "%~dp0venv\Scripts\pythonw.exe" (
    set "PYW_CMD=%~dp0venv\Scripts\pythonw.exe"
) else if exist "C:\Program Files\Python38\pythonw.exe" (
    set "PYW_CMD=C:\Program Files\Python38\pythonw.exe"
) else (
    where pythonw >nul 2>&1 && set "PYW_CMD=pythonw"
)
if not defined PYW_CMD set "PYW_CMD=%PY_CMD%"

:: 5. Limpiar registro de errores previo
if exist "error_panel_critico.txt" del /f /q "error_panel_critico.txt" >nul 2>&1

:: 6. Verificar e instalar automáticamente dependencias web (Flask y Flask-Cors)
"%PY_CMD%" -c "import flask, flask_cors" >nul 2>&1
if %errorlevel% neq 0 (
    echo ======================================================================
    echo [CONFIGURACION] Instalando Flask y Flask-Cors en el entorno...
    echo ======================================================================
    "%PY_CMD%" -m pip install flask flask-cors
)

echo ======================================================================
echo    BOT UNIVERSIDAD ONLINE - PANEL DE CONTROL WEB INTERACTIVO
echo    Iniciando servidor local en segundo plano (http://127.0.0.1:8000)...
echo ======================================================================
echo.

start "" "%PYW_CMD%" dashboard_web.py

:: Breve espera para verificar si hubo fallo prematuro
timeout /t 2 >nul

if exist "error_panel_critico.txt" (
    color 0C
    echo ======================================================================
    echo ⚠️ ERROR AL INICIAR EL PANEL DE CONTROL:
    type "error_panel_critico.txt"
    echo.
    echo ======================================================================
    pause
    exit /b 1
)

echo [OK] Panel de control iniciado en segundo plano exitosamente.
echo [OK] Abriendo navegador predeterminado en http://127.0.0.1:8000 ...
timeout /t 1 >nul
exit
