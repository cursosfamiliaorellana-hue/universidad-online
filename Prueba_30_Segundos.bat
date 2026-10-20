@echo off
chcp 1252 >nul
title Bot Universidad Online - Prueba en Vivo Completa Fase 3
color 0E

cd /d "%~dp0"
set "PYTHONPATH=%~dp0libs"
set "NODE_SKIP_PLATFORM_CHECK=1"

echo ======================================================================
echo    PRUEBA EN VIVO COMPLETA (60 SEGUNDOS) - MASTERCLASS REAL DE HOY
echo ======================================================================
echo.
echo 1. Deteccion automatica de la Masterclass mas proxima o activa de hoy.
echo 2. Conexion CDP a Hotmart (busqueda inteligente, navegacion y play).
echo 3. Actualizacion en tiempo real en Google Calendar.
echo 4. Grabacion digital pura de 60 segundos (inmune a ventanas superpuestas).
echo 5. Extraccion de audio ligero .mp3 para voz.
echo 6. Analisis en la nube con Gemini (Semaforo Pareto, Infografia, Quizzes).
echo 7. Sincronizacion en NotebookLM.
echo 8. Generacion de imagenes PNG de alta resolucion (Infografia y Mapa Mental).
echo 9. Actualizacion instantanea del Tablero Dinamico y App Web (PWA).
echo 10. Publicacion limpia en Telegram: Video MP4 + Audio Resumen (Podcast).
echo     (Quizzes interactivos, infografias y checklists se consultan en la App Web).
echo.
echo NOTA: Asegurate de tener abierta la ventana de 1_Abrir_Chrome_Hotmart.bat
echo ======================================================================
echo.

"C:\Program Files\Python38\python.exe" prueba_30_segundos.py

echo.
echo ======================================================================
echo Fin de la prueba en vivo.
echo ======================================================================
pause