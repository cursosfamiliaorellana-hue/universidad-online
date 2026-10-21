@echo off
chcp 65001 >nul
title Autenticar Telegram - Bot Universidad Online

cd /d "%~dp0"

:: 1. Activar entorno virtual si existe
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

:: 2. Asegurar PYTHONPATH incluyendo raíz y carpeta libs
set "PYTHONPATH=%~dp0;%~dp0libs;%PYTHONPATH%"

:: 3. Detectar ejecutable de Python compatible
set "PY_CMD="
if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0venv\Scripts\python.exe"
) else if exist "C:\Program Files\Python38\python.exe" (
    set "PY_CMD=C:\Program Files\Python38\python.exe"
) else (
    set "PY_CMD=python"
)

echo ======================================================================
echo          AUTENTICACION DE TELEGRAM (Telethon)
echo ======================================================================
echo.
echo Ingresa tu numero de telefono con codigo de pais (ejemplo: +591XXXXXXXX).
echo Luego ingresa el codigo de verificacion que Telegram te enviara a tu app.
echo.
echo La sesion se guardara localmente como 'sesion_telegram.session'.
echo ======================================================================
echo.

"%PY_CMD%" telegram_uploader.py --login

echo.
echo ======================================================================
pause
