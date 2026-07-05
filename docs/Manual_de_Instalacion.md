# Manual de Instalación

Este documento detalla las tecnologías utilizadas en el simulador PatatOS y los pasos para compilarlo y ejecutarlo localmente.

## 1. Tecnologías Utilizadas

| Componente | Tecnología | Descripción |
| :--- | :--- | :--- |
| **Motor de simulación** | C++23 | Usado para simular la lógica y el rendimiento. Compatible con GCC, Clang y MSVC. |
| **Sistema de compilación** | CMake / Batch | Usado para facilitar la compilación del código de C++ en múltiples plataformas. |
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

## 3. Compilación Rápida del Backend (Solo Windows)
Si estás en Windows y tienes `g++` configurado en tus variables de entorno, hemos preparado un script de compilación automática para que no tengas que lidiar con comandos. Simplemente haz doble clic sobre el archivo:
```text
compilar_backend.bat
```
Esto recompilará todo el motor C++ automáticamente y generará el ejecutable `simulator.exe` dentro de la carpeta `backend/`.

## 4. Compilación del Backend (CMake Multiplataforma)
El código fuente del motor de simulación se encuentra en la carpeta `backend`. Para compilarlo de forma tradicional, usa una terminal y ejecuta:
```bash
cd backend
mkdir build && cd build
cmake ..
cmake --build .
```
Esto creará el archivo ejecutable `simulator` dentro del directorio de construcción. 

## 5. Ejecución por Consola
Si deseas usar solo el backend, puedes ejecutar la simulación desde la terminal indicando los archivos JSON:
```bash
./simulator -i input.json -o output.json -t 50000
```
**Parámetros:**
- `-i <archivo>`: Ruta del archivo JSON de configuración y entrada.
- `-o <archivo>`: Ruta del archivo JSON donde se guardarán los resultados.
- `-t <ticks>`: Cantidad máxima de ticks a ejecutar antes de detener el simulador por seguridad.
- `-h`: Muestra el menú de ayuda.

## 6. Ejecución con la Interfaz Gráfica (Frontend)
Para iniciar el simulador completo con su interfaz de usuario, la manera recomendada y automática (en Windows) es hacer doble clic en el lanzador ubicado en la raíz del proyecto:
```text
iniciar_patatos.bat
```
Este script se encargará automáticamente de:
1. Verificar que Python esté instalado.
2. Instalar o verificar las dependencias (`PySide6`, `psutil`) requeridas.
3. Compilar automáticamente el motor C++ si aún no existe.
4. Ejecutar la interfaz gráfica.

Si estás en otro sistema operativo o prefieres hacerlo manualmente, abre una terminal y ejecuta:
```bash
cd frontend
python main.py
```
Aparecerá el menú de configuración principal (donde puedes elegir entre memoria contigua o memoria virtual), desde el cual la interfaz se encargará de invocar al ejecutable C++ automáticamente en segundo plano.

## 7. Pruebas y Benchmarking Automatizado
Si quieres realizar un análisis de rendimiento comparando algoritmos (FCFS, SJF, SRTF, RR, Priority) y estrategias de memoria sin abrir la interfaz gráfica, usa el script de benchmarking en la raíz del proyecto:
```bash
python run_benchmark.py
```
Este script configurará temporalmente los archivos JSON, ejecutará el motor en segundo plano y te mostrará tablas con métricas (como uso de CPU, tiempos de espera promedio y fragmentación máxima) en tu consola.
