@echo off
chcp 1252 >nul
title Bot Universidad Online - Programador Manual
color 0E

cd /d "%~dp0"
set "PYTHONPATH=%~dp0libs"

"C:\Program Files\Python38\python.exe" programador_manual.py

pause