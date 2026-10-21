@echo off
chcp 1252 >nul
title Bot Universidad Online - Detener Sistema
color 0C

echo ======================================================================
echo    DETENIENDO BOT UNIVERSIDAD ONLINE Y PROCESOS RESIDUALES
echo ======================================================================
echo.

echo [1/3] Finalizando procesos de transmision y grabacion (FFmpeg)...
taskkill /F /IM ffmpeg.exe 2>nul

echo [2/3] Finalizando ventanas y procesos de Python asociados...
taskkill /F /FI "WINDOWTITLE eq Bot Universidad Online*" 2>nul
taskkill /F /IM python.exe 2>nul
taskkill /F /IM pythonw.exe 2>nul

echo [3/3] Finalizando posibles procesos de fondo residuales...
taskkill /F /IM cloudflared.exe 2>nul

echo.
echo ======================================================================
echo [OK] Todos los procesos del sistema se han detenido limpiamente.
echo ======================================================================
pause
