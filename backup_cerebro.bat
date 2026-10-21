@echo off
chcp 1252 >nul
title Bot Universidad Online - Respaldo Cerebro Anti-Desastres (Disaster Recovery)
color 0A

cd /d "%~dp0"

echo ======================================================================
echo    BOT UNIVERSIDAD ONLINE - PROTOCOLO DE DISASTER RECOVERY
echo    Respaldo de Base de Datos (clases.db), Metadata y Codigo Fuente
echo ======================================================================
echo.

:: 1. Generar marca de tiempo precisa para el respaldo
for /f "tokens=*" %%a in ('powershell -NoProfile -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"') do set "TS=%%a"

if not defined TS (
    set "TS=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%"
    set "TS=%TS: =0%"
)

:: 2. Crear carpeta de respaldos locales si no existe
if not exist "_backups_db" (
    mkdir "_backups_db"
    echo [+] Carpeta _backups_db creada.
)

:: 3. Copia de seguridad local instantánea de clases.db
if exist "clases.db" (
    copy /y "clases.db" "_backups_db\clases_backup_%TS%.db" >nul
    echo [OK] Copia local de clases.db guardada: _backups_db\clases_backup_%TS%.db
) else (
    echo [!] AVISO: No se encontro el archivo clases.db en la raiz.
)

:: 4. Copia de seguridad local de config.json si existe
if exist "config.json" (
    copy /y "config.json" "_backups_db\config_backup_%TS%.json" >nul
    echo [OK] Copia local de configuracion guardada: _backups_db\config_backup_%TS%.json
)

echo.
echo ======================================================================
echo Sincronizando respaldo seguro con GitHub (Disaster Recovery Cloud)...
echo ======================================================================

:: 5. Detectar ejecutable de Git (Prioridad: Git portable local en z:\git\cmd\git.exe)
set "GIT_EXE="
if exist "%~dp0git\cmd\git.exe" set "GIT_EXE=%~dp0git\cmd\git.exe"
if not defined GIT_EXE where git >nul 2>&1 && set "GIT_EXE=git"
if not defined GIT_EXE if exist "C:\Program Files\Git\cmd\git.exe" set "GIT_EXE=C:\Program Files\Git\cmd\git.exe"
if not defined GIT_EXE if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" set "GIT_EXE=%LOCALAPPDATA%\Programs\Git\cmd\git.exe"

if not defined GIT_EXE (
    echo [AVISO] Git no fue detectado en el sistema. El respaldo local en _backups_db esta asegurado.
    goto final
)

:: 6. Asegurar safe.directory para evitar errores de ownership en Windows
"%GIT_EXE%" config --global --add safe.directory "*" >nul 2>&1

:: 7. Cargar credenciales desde .env si existe
set "ENV_TOKEN="
set "ENV_REPO="
if exist "%~dp0.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0.env") do (
        if "%%A"=="GITHUB_TOKEN" set "ENV_TOKEN=%%B"
        if "%%A"=="GITHUB_REPO_URL" set "ENV_REPO=%%B"
    )
)

:: 8. Configurar URL autenticada si hay token en .env
if defined ENV_TOKEN if defined ENV_REPO (
    powershell -NoProfile -Command ^
        "$t = '%ENV_TOKEN%'.Trim(); $r = '%ENV_REPO%'.Trim();" ^
        "if ($t -and $r) { $auth = $r -replace 'https?://([^@]+@)?', ('https://' + $t + '@'); & '%GIT_EXE%' remote set-url origin $auth }" >nul 2>&1
)

:: 9. Ejecutar Add, Commit y Push respetando .gitignore (Cero videos, Cero .env)
if exist ".git" (
    echo [OK] Repositorio Git detectado. Indexando codigo fuente y clases.db...
    "%GIT_EXE%" add .
    "%GIT_EXE%" commit -m "Respaldo automatico cerebro [%TS%]" >nul 2>&1
    echo [OK] Enviando cambios a GitHub en rama main...
    "%GIT_EXE%" push origin main
    if %errorlevel% equ 0 (
        echo [OK] Respaldo en la nube con GitHub completado exitosamente.
    ) else (
        echo [AVISO] Git push no pudo completarse. Si cambiaste tu token, ejecuta '6_Conectar_Con_GitHub.bat'.
    )
) else (
    echo [INFO] Repositorio Git no inicializado. Ejecuta '6_Conectar_Con_GitHub.bat' para vincularlo.
)

:final
echo.
echo ======================================================================
echo    PROTOCOLO DE RESPALDO COMPLETADO CON EXITO
echo ======================================================================
pause
