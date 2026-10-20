@echo off
chcp 65001 >nul
title Servidor Local PWA - Universidad Online
cls
echo ======================================================================
echo    COMPARTIR PLATAFORMA WEB DIDACTICA CON TU CELULAR (MISMA RED WI-FI)
echo ======================================================================
echo.
echo Para abrir la aplicacion en tu celular o tablet:
echo 1. Asegurate de que tu celular este conectado a la misma red Wi-Fi.
echo 2. Abre Google Chrome o Safari en tu celular.
echo 3. Escribe en la barra de direcciones una de las siguientes opciones:
echo.

for /f "tokens=4" %%a in ('route print^|findstr 0.0.0.0.*0.0.0.0') do (
    set LOCAL_IP=%%a
)

echo    👉 http://localhost:8080/app_web/  (Para verla en esta computadora)
if defined LOCAL_IP (
    echo    👉 http://%LOCAL_IP%:8080/app_web/  (Para verla en tu celular o tablet)
) else (
    echo    👉 http://[TU_IP_LOCAL]:8080/app_web/
)
echo.
echo 4. En tu celular, pulsa el boton "📲 Instalar App" o en el menu de Chrome
echo    selecciona "Añadir a pantalla de inicio" para tener el icono de la app.
echo.
echo [NOTA] Para detener el servidor, simplemente cierra esta ventana negra.
echo ======================================================================
echo Iniciando servidor en el puerto 8080...
echo ======================================================================
python -m http.server 8080
pause
