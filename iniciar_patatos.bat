@echo off
title PatatOS - Lanzador
echo =======================================================
echo             Iniciando PatatOS (Frontend)
echo =======================================================
echo.

:: 1. Verificar si Python esta instalado
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python no esta instalado o no esta agregado al PATH de Windows.
    echo Por favor, descarga e instala Python 3.8 o superior desde python.org
    echo Asegurate de marcar la casilla "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

:: 2. Instalar/Verificar dependencias automaticamente
echo [INFO] Verificando e instalando dependencias (PySide6, psutil)...
pip install -r frontend\requirements.txt -q
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Hubo un problema al verificar las dependencias con pip.
    echo Intentando abrir el programa de todas formas...
) else (
    echo [OK] Dependencias instaladas y actualizadas.
)

:: 3. Verificar si el motor C++ ya esta compilado
if not exist "backend\simulator.exe" (
    echo.
    echo [INFO] No se encontro el motor 'simulator.exe' en la carpeta 'backend\'.
    echo [INFO] Ejecutando el script de compilacion automaticamente...
    call compilar_backend.bat
)

:: 4. Lanzar la interfaz grafica
echo.
echo [INFO] Lanzando la interfaz grafica de PatatOS...
cd frontend
python main.py

:: Si el programa se cierra por un error, pausar para que el usuario pueda leerlo
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] El frontend se cerro inesperadamente.
    pause
)
