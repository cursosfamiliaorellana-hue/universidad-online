@echo off
chcp 65001 >nul
title Bot Universidad Online - Instalación de Requisitos en Nueva PC
color 0B

echo ======================================================================
echo       BOT UNIVERSIDAD ONLINE - CONFIGURACIÓN EN NUEVA PC
echo       Compatible con Windows 8, Windows 10 y Windows 11
echo ======================================================================
echo.

:: 1. Verificar si Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python no está instalado o no se encuentra en la variable PATH.
    echo.
    echo Por favor descarga e instala Python:
    echo  - Si tu PC es Windows 8 / 8.1: Instala Python 3.8.10 (32 o 64 bit).
    echo    Descarga oficial: https://www.python.org/downloads/release/python-3810/
    echo    IMPORTANTE: Marca la casilla "Add Python 3.8 to PATH" durante la instalación.
    echo.
    echo  - Si tu PC es Windows 10 u 11: Instala Python 3.10 o superior marcando "Add to PATH".
    echo ======================================================================
    pause
    exit /b 1
)

echo [1/4] Verificando versión de Python...
python --version
echo.

:: 2. Actualizar pip
echo [2/4] Actualizando instalador de paquetes pip...
python -m pip install --upgrade pip --quiet
echo.

:: 3. Instalar librerías de requirements.txt con precompilados (--prefer-binary)
echo [3/4] Instalando librerías requeridas (requests, telethon, playwright, pytz, etc.)...
python -m pip install --prefer-binary -r requirements.txt
if %errorlevel% neq 0 (
    color 0E
    echo [AVISO] Ocurrió un error al instalar algunos paquetes. Reintentando con banderas de compatibilidad...
    python -m pip install --only-binary :all: -r requirements.txt
)
echo.

:: 4. Instalar Chromium para Playwright
echo [4/4] Verificando e instalando dependencias de navegador Playwright...
python -m playwright install chromium
echo.

:: 5. Verificar FFmpeg local
if not exist "%~dp0ffmpeg.exe" (
    color 0E
    echo [AVISO IMPORTANTE] No se encontró ffmpeg.exe en esta carpeta:
    echo  "%~dp0ffmpeg.exe"
    echo  Asegúrate de copiar el archivo ffmpeg.exe a esta carpeta para poder grabar video y audio.
    echo.
) else (
    echo [OK] ffmpeg.exe detectado correctamente en la carpeta del bot.
    echo.
)

:: 6. Recordatorio de credenciales y perfiles
echo ======================================================================
echo                     INSTALACIÓN FINALIZADA CON ÉXITO
echo ======================================================================
echo.
echo Pasos a seguir para activar el bot en esta computadora:
echo.
echo 1. Si aún no lo has hecho, ejecuta:
echo       Login_Telegram.bat
echo    para autenticar tu cuenta de Telegram una sola vez.
echo.
echo 2. Para el uso diario:
echo       - Abre: 1_Abrir_Chrome_Hotmart.bat
echo         (Inicia sesión en Hotmart y abre NotebookLM en esa misma ventana)
echo       - Abre: 2_Iniciar_Bot_Automatico.bat
echo         (Dejará el bot vigilando los horarios y grabando en automático)
echo.
echo ======================================================================
pause
