@echo off
:: Evitamos que el script se llame a si mismo accidentalmente
setlocal enabledelayedexpansion
title ScrappyDoo - SENAMHI Scraper - Control de Entorno

echo ====================================================
echo   SENAMHI SCRAPER - VERIFICADOR DE ENTORNO
echo ====================================================

:: 1. Verificar si Edge ya esta abierto en modo depuracion (Puerto 9222)
netstat -ano | findstr :9222 >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Edge no esta en modo depuracion. Intentando abrir...
    start msedge.exe --remote-debugging-port=9222 --user-data-dir="C:\edge-debug-profile"
    echo [*] Esperando a que Edge inicie...
    timeout /t 5 /nobreak >nul
) else (
    echo [OK] Sesion de Edge detectada en puerto 9222.
)

:: 2. Verificar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python no encontrado. Instale Python 3.10+ y agreguelo al PATH.
    pause
    exit /b
)

:: 3. Entorno Virtual
if not exist "venv" (
    echo [*] Creando entorno virtual...
    python -m venv venv
)

:: 4. Instalacion de librerias (Uso de python -m pip para evitar conflictos)
echo [*] Verificando dependencias...
call venv\Scripts\activate
python -m pip install --upgrade pip >nul
python -m pip install requests beautifulsoup4 playwright customtkinter >nul

:: Asegurar que Playwright tenga sus drivers
echo [*] Verificando drivers de navegacion...
python -m playwright install edge

:: 5. Ejecucion
echo ====================================================
echo   INICIANDO APLICACION...
echo ====================================================
:: IMPORTANTE: Asegurate que tu archivo de interfaz se llame exactamente gui_app.py
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [!] La aplicacion se detuvo inesperadamente.
    pause
)

deactivate