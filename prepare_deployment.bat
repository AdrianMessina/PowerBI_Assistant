@echo off
title Preparar Deployment - PBI CLI Chat
echo ========================================
echo   Preparando deployment para Cloudera
echo ========================================
echo.

cd /d "%~dp0"

echo [1/5] Limpiando archivos temporales...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul

echo [2/5] Limpiando logs y uploads locales...
if exist logs\ rd /s /q logs
if exist uploads\ rd /s /q uploads
if exist .env del .env

echo [3/5] Verificando archivos criticos...
set MISSING=0

if not exist .project-metadata.yaml (
    echo [ERROR] Falta: .project-metadata.yaml
    set MISSING=1
)
if not exist requirements.txt (
    echo [ERROR] Falta: requirements.txt
    set MISSING=1
)
if not exist cml\launch_app.py (
    echo [ERROR] Falta: cml\launch_app.py
    set MISSING=1
)
if not exist server.py (
    echo [ERROR] Falta: server.py
    set MISSING=1
)
if not exist index.html (
    echo [ERROR] Falta: index.html
    set MISSING=1
)

if %MISSING%==1 (
    echo.
    echo [ERROR] Faltan archivos criticos. Verifica la estructura.
    pause
    exit /b 1
)

echo [OK] Todos los archivos criticos presentes

echo [4/5] Creando archivo ZIP para upload...
powershell -Command "Compress-Archive -Path * -DestinationPath ..\pbi-cli-chat.zip -Force"

if exist ..\pbi-cli-chat.zip (
    echo [OK] ZIP creado: pbi-cli-chat.zip
) else (
    echo [ERROR] No se pudo crear el ZIP
    pause
    exit /b 1
)

echo [5/5] Calculando tamano...
for %%A in (..\pbi-cli-chat.zip) do echo Tamano: %%~zA bytes (~%%~zA KB)

echo.
echo ========================================
echo   LISTO PARA DEPLOYMENT
echo ========================================
echo.
echo Archivo: ..\pbi-cli-chat.zip
echo.
echo Proximos pasos:
echo   1. Ir a Cloudera AI Workbench
echo   2. Applications ^> New Application
echo   3. Subir: pbi-cli-chat.zip
echo   4. Cloudera detectara .project-metadata.yaml
echo   5. Start Application
echo.
echo Documentacion: README_CLOUDERA.md
echo Checklist: DEPLOYMENT_CHECKLIST.md
echo.
pause
