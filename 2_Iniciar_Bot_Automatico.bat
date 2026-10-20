@echo off
chcp 1252 >nul
title Bot Universidad Online - Orquestador Automatico Inteligente (Fase 3)
color 0A

cd /d "%~dp0"
set "PYTHONPATH=%~dp0libs"
set "NODE_SKIP_PLATFORM_CHECK=1"

echo ======================================================================
echo       BOT UNIVERSIDAD ONLINE - SISTEMA INTELIGENTE DE APRENDIZAJE
echo       (Pareto 80/20 + NotebookLM AI + Infografias + Rutas Dinamicas)
echo ======================================================================
echo.
echo 1. Sincronizacion continua de clases con Google Calendar.
echo 2. Grabacion limpia con foco exclusivo en Chrome (sin ventanas superpuestas).
echo 3. Extraccion de audio ligero .mp3 para voz (~15 MB/hora).
echo 4. Analisis en la nube con Gemini: Semaforo Pareto 80/20, Infografia y Quizzes.
echo 5. Cuadernos aislados (UO - ...) y Podcasts en NotebookLM via navegador.
echo 6. Generacion del Tablero Interactivo y App Web: Mis_Rutas_80_20_UniversidadOnline.html.
echo 7. Publicacion limpia en Telegram: Video MP4 + Audio Resumen (Podcast).
echo    (Quizzes interactivos, infografias y checklists se consultan en la App Web).
echo.
echo NOTA: Manten abierta la ventana iniciada con 1_Abrir_Chrome_Hotmart.bat
echo ======================================================================
echo.

"C:\Program Files\Python38\python.exe" main.py

echo.
echo ======================================================================
echo El proceso del Bot ha finalizado.
echo ======================================================================
pause