@echo off
title Iniciando Panel Web...
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "env\Scripts\activate.bat" (
    call env\Scripts\activate.bat
) else (
    echo [AVISO] No se encontro carpeta de entorno virtual. Usando Python del sistema.
)

echo Instalando dependencias web si faltan...
pip install flask flask-cors >nul 2>&1

echo Encendiendo Panel Web (Modo Consola Visible)...
python dashboard_web.py
pause
exit
