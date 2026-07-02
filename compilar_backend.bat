@echo off
echo =======================================================
echo     Compilando el Motor de Simulacion PatatOS (C++)
echo =======================================================
echo.

cd backend
echo Ejecutando g++...
g++ -std=c++23 -Iinclude -Isrc -O3 src/*.cpp -o simulator.exe

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [EXITO] Compilacion exitosa. 
    echo [EXITO] El ejecutable 'simulator.exe' ha sido generado dentro de la carpeta 'backend\'.
) else (
    echo.
    echo [ERROR] Hubo un error durante la compilacion. Revisa la salida de la consola.
)

echo.
pause
