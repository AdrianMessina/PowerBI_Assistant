@echo off
title PBI CLI — Power BI Assistant
echo.
echo   =============================================
echo     PBI CLI — Power BI + AI
echo     Abriendo en el navegador...
echo     Ctrl+C para cerrar
echo   =============================================
echo.
cd /d "%~dp0"
python server.py
pause
