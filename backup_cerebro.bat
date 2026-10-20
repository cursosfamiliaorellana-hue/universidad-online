@echo off
chcp 1252 >nul
title Bot Universidad Online - Respaldo Cerebro Anti-Desastres
color 0A

cd /d "%~dp0"

echo ======================================================================
echo    BOT UNIVERSIDAD ONLINE - PROTOCOLO DE DISASTER RECOVERY
echo    Respaldo de Base de Datos (clases.db) y Configuracion
echo ======================================================================
echo.

:: 1. Generar marca de tiempo precisa
for /f "tokens=*" %%a in ('powershell -NoProfile -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"') do set "TS=%%a"

if not defined TS (
    set "TS=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%"
    set "TS=%TS: =0%"
)

:: 2. Crear carpeta de respaldos si no existe
if not exist "_backups_db" (
    mkdir "_backups_db"
    echo [+] Carpeta _backups_db creada.
)

:: 3. Copia de seguridad de clases.db
if exist "clases.db" (
    copy /y "clases.db" "_backups_db\clases_backup_%TS%.db" >nul
    echo [OK] Copia de seguridad creada: _backups_db\clases_backup_%TS%.db
) else (
    echo [!] AVISO: No se encontro el archivo clases.db en la raiz.
)

:: 4. Copia de seguridad de config.json
if exist "config.json" (
    copy /y "config.json" "_backups_db\config_backup_%TS%.json" >nul
    echo [OK] Copia de configuracion: _backups_db\config_backup_%TS%.json
)

echo.
echo ======================================================================
echo Verificando sincronizacion remota con Git...
echo ======================================================================

:: 5. Detectar ejecutable de Git
set "GIT_EXE="
where git >nul 2>&1 && set "GIT_EXE=git"
if not defined GIT_EXE if exist "%~dp0git\cmd\git.exe" set "GIT_EXE=%~dp0git\cmd\git.exe"
if not defined GIT_EXE if exist "C:\Program Files\Git\cmd\git.exe" set "GIT_EXE=C:\Program Files\Git\cmd\git.exe"
if not defined GIT_EXE if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" set "GIT_EXE=%LOCALAPPDATA%\Programs\Git\cmd\git.exe"

if defined GIT_EXE (
    if exist ".git" (
        echo [OK] Repositorio Git detectado. Sincronizando clases.db y metadata...
        "%GIT_EXE%" add clases.db data.json database.json
        "%GIT_EXE%" commit -m "Disaster Recovery Cerebro Backup [%TS%]"
        "%GIT_EXE%" push origin main
        echo [OK] Respaldo en la nube con GitHub completado exitosamente.
    ) else (
        echo [INFO] No se detecto un repositorio git local. Respaldo guardado en _backups_db.
    )
) else (
    echo [INFO] Git no detectado en el sistema. Respaldo completado localmente en _backups_db.
)

echo.
echo ======================================================================
echo    PROTOCOLO DE RESPALDO COMPLETADO CON EXITO
echo ======================================================================
pause
