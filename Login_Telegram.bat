@echo off
chcp 65001 >nul
title Autenticar Telegram - Bot Universidad Online

cd /d "%~dp0"

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

python telegram_uploader.py --login

echo.
echo ======================================================================
pause
