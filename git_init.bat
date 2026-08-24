@echo off
title Git Setup - PBI CLI Chat
echo ========================================
echo   Git Repository Setup
echo ========================================
echo.

cd /d "%~dp0"

REM Check if Git is available
where git >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Git no esta instalado o no esta en el PATH
    echo.
    echo Opciones:
    echo   1. Instalar Git: https://git-scm.com/download/win
    echo   2. Usar GitHub Desktop: https://desktop.github.com/
    echo   3. Agregar Git al PATH
    echo.
    echo Consulta: GIT_SETUP.md para instrucciones detalladas
    pause
    exit /b 1
)

echo [OK] Git encontrado
git --version
echo.

REM Check if already a git repo
if exist .git\ (
    echo [INFO] Ya existe un repositorio Git
    git status
    echo.
    set /p continue="Continuar? (S/N): "
    if /i not "%continue%"=="S" exit /b 0
) else (
    echo [1/4] Inicializando repositorio Git...
    git init
    echo [OK] Repositorio inicializado
)

echo.
echo [2/4] Agregando archivos...
git add .

echo.
echo [3/4] Creando commit inicial...
git commit -m "feat: Initial commit - PBI CLI Chat

- Chat conversacional con Claude AI
- Integracion pbi-cli
- Configuracion Cloudera
- API de descubrimiento masivo PBIP
- Modo normal y masivo (en desarrollo)
"

if %ERRORLEVEL% EQU 0 (
    echo [OK] Commit creado exitosamente
) else (
    echo [WARN] No se pudo crear commit o no hay cambios
)

echo.
echo [4/4] Configurando rama principal...
git branch -M main

echo.
echo ========================================
echo   REPOSITORIO LISTO
echo ========================================
echo.
echo Proximos pasos:
echo.
echo 1. CREAR REPOSITORIO en GitHub/GitLab:
echo    - GitHub: https://github.com/new
echo    - GitLab: https://gitlab.com/projects/new
echo    Nombre sugerido: pbi-cli-chat
echo    Visibilidad: Private
echo.
echo 2. CONECTAR con el repositorio remoto:
echo    git remote add origin https://github.com/TU_USUARIO/pbi-cli-chat.git
echo.
echo 3. SUBIR el codigo:
echo    git push -u origin main
echo.
echo 4. OBTENER URL para Cloudera:
echo    La URL sera: https://github.com/TU_USUARIO/pbi-cli-chat.git
echo.
echo Documentacion completa: GIT_SETUP.md
echo.
pause
