# Manual de Instalación

Este documento detalla las tecnologías utilizadas en el simulador PatatOS y los pasos para compilarlo y ejecutarlo localmente.

## 1. Tecnologías Utilizadas

| Componente | Tecnología | Descripción |
| :--- | :--- | :--- |
| **Motor de simulación** | C++23 | Usado para simular la lógica y el rendimiento. Compatible con GCC, Clang y MSVC. |
| **Sistema de compilación** | CMake | Usado para facilitar la compilación del código de C++ en múltiples plataformas. |
| **Librería JSON** | nlohmann/json | Usado en C++ para parsear la configuración y exportar resultados. |
| **Interfaz gráfica** | Python 3 + PySide6 | Usado para la interfaz de escritorio (Qt 6). |
| **Renderizado gráfico** | QPainter | Usado para dibujar los diagramas personalizados (memoria, Gantt, tabla PCB). |

## 2. Requisitos previos
Para ejecutar este proyecto, necesitas instalar:
- Un compilador con soporte para C++23 (GCC 11+, Clang 14+, MSVC 2022+)
- CMake 3.15 o superior
- Python 3.8 o superior
- Librerías de Python requeridas (puedes instalarlas mediante pip):
  ```bash
  pip install PySide6
  pip install psutil
  ```

## 3. Compilación del Backend (C++)
El código fuente del motor de simulación se encuentra en la carpeta `backend`. Para compilarlo, usa una terminal y ejecuta:
```bash
cd backend
mkdir build && cd build
cmake ..
cmake --build .
```
Esto creará el archivo ejecutable `simulator` (o `simulator.exe` en Windows) dentro del directorio de construcción. En los entornos ya configurados, también puede compilarse directamente usando g++.

## 4. Ejecución por Consola
Si deseas usar solo el backend, puedes ejecutar la simulación desde la terminal indicando los archivos JSON:
```bash
./simulator -i input.json -o output.json -t 50000
```
**Parámetros:**
- `-i <archivo>`: Ruta del archivo JSON de configuración y entrada.
- `-o <archivo>`: Ruta del archivo JSON donde se guardarán los resultados.
- `-t <ticks>`: Cantidad máxima de ticks a ejecutar antes de detener el simulador por seguridad.
- `-h`: Muestra el menú de ayuda.

## 5. Ejecución con la Interfaz Gráfica (Frontend)
Para ejecutar el simulador completo con su interfaz de usuario, abre una terminal en la raíz del proyecto y ejecuta:
```bash
cd frontend
python main.py
```
## 6. Pruebas y Benchmarking Automatizado
Si quieres realizar un análisis de rendimiento comparando algoritmos (FCFS, SJF, SRTF, RR, Priority) y estrategias de memoria sin abrir la interfaz gráfica, usa el script de benchmarking en la raíz del proyecto:
```bash
python run_benchmark.py
```
Este script configurará temporalmente los archivos JSON, ejecutará el motor en segundo plano y te mostrará tablas con métricas (como uso de CPU, tiempos de espera promedio y fragmentación máxima) en tu consola.
