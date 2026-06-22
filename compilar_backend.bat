@echo off
echo =======================================================
echo     Compilando el Motor de Simulacion PatatOS (C++)
echo =======================================================
echo.

cd backend
echo Ejecutando g++...
g++ -std=c++17 -Iinclude -Isrc -O3 src/main.cpp src/scheduler.cpp src/dispatcher.cpp src/memory_manager.cpp src/io_manager.cpp src/error_manager.cpp src/json_reader.cpp src/json_writer.cpp src/simulator.cpp -o simulator.exe

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
