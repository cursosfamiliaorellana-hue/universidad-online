@echo off
title Encendido Maestro - Bot Universidad Online
cd /d "%~dp0"
set "NODE_SKIP_PLATFORM_CHECK=1"

echo ========================================================
echo   Encendido Maestro - Bot Universidad Online
echo ========================================================
echo.

echo [1/4] Limpiando procesos previos...
taskkill /F /IM pythonw.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1

echo [2/4] Preparando entorno de Chrome con Depuracion Remota...
set "USER_DATA_DIR=%~dp0perfil_chrome"
if not exist "%USER_DATA_DIR%" mkdir "%USER_DATA_DIR%"

set "CHROME_EXE="
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    set "CHROME_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
) else if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
)
if "%CHROME_EXE%"=="" (
    where chrome.exe >nul 2>&1
    if %ERRORLEVEL% equ 0 set "CHROME_EXE=chrome.exe"
)
if "%CHROME_EXE%"=="" set "CHROME_EXE=chrome.exe"

echo [3/4] Iniciando Chrome en Puerto 9222 y abriendo Panel Web + Hotmart...
start "" "%CHROME_EXE%" --remote-debugging-port=9222 --remote-debugging-address=0.0.0.0 --user-data-dir="%USER_DATA_DIR%" --remote-allow-origins=* --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --autoplay-policy=no-user-gesture-required "http://127.0.0.1:8000" "https://hotmart.com/es/club/suscripcionuniversidadonline/products/7048143"

echo Dando 4 segundos a Chrome para inicializar puerto de depuracion...
timeout /t 4 /nobreak >nul

echo [4/5] Verificando entorno de dependencias...
python -c "import requests, flask, flask_cors, schedule, pytz" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [Auto-Sanacion] Instalando dependencias requeridas...
    python -m pip install --prefer-binary -r requirements.txt --quiet
)

echo [5/5] Encendiendo Motores Python (Modo Fantasma 100% Invisible)...
start "" pythonw dashboard_web.py
start "" pythonw vigia_mentorias.py
start "" pythonw main.py

exit
