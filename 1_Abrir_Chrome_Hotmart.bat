@echo off
chcp 65001 >nul
title Bot Universidad Online - Chrome con Remote Debugging (Hotmart)

echo ========================================================
echo   Iniciando Google Chrome con Remote Debugging (9222)
echo ========================================================
echo.

set "USER_DATA_DIR=%~dp0perfil_chrome"

if not exist "%USER_DATA_DIR%" (
    echo Creando directorio de perfil local: "%USER_DATA_DIR%"
    mkdir "%USER_DATA_DIR%"
)

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
    if %ERRORLEVEL% equ 0 (
        set "CHROME_EXE=chrome.exe"
    )
)

if "%CHROME_EXE%"=="" (
    echo [ERROR] No se pudo encontrar google chrome en las rutas habituales.
    echo Por favor asegurate de tener Google Chrome instalado.
    pause
    exit /b 1
)

echo Usando ejecutable: "%CHROME_EXE%"
echo Perfil de usuario: "%USER_DATA_DIR%"
echo Puerto de depuracion: 9222
echo.
echo Abriendo Hotmart para inicio de sesion manual...

start "" "%CHROME_EXE%" --remote-debugging-port=9222 --user-data-dir="%USER_DATA_DIR%" --remote-allow-origins=* --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --autoplay-policy=no-user-gesture-required "https://hotmart.com/es/club/suscripcionuniversidadonline/products/7048143" "https://notebooklm.google.com/"

echo.
echo [LISTO] Chrome ha sido lanzado con exito en el puerto 9222.
echo Ahora inicia sesion manualmente en Hotmart en la ventana que se abrio.
echo.
pause
