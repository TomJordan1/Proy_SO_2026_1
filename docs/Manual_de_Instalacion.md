# Manual de Instalación

Este documento detalla las tecnologías utilizadas en el simulador PatatOS y los pasos necesarios para instalarlo y compilarlo en un entorno local.

## 1. Tecnologías y Framework Utilizados

| Componente | Tecnología | Versión / Justificación |
| :--- | :--- | :--- |
| **Motor de simulación** | C++17 | GCC/Clang/MSVC compatible. Rendimiento óptimo para el procesamiento tick a tick. |
| **Sistema de compilación** | CMake | 3.15+. Portabilidad y gestión de dependencias multiplataforma. |
| **Librería JSON** | nlohmann/json | header-only. Librería estándar de facto para JSON en C++. |
| **Interfaz gráfica** | Python 3 + PySide6 | Qt 6. Framework maduro para interfaces de escritorio con capacidades gráficas. |
| **Renderizado gráfico** | QPainter | integrado en Qt. Permite dibujo personalizado de diagramas de memoria, Gantt y estados. |

## 2. Requisitos previos
Para poder ejecutar este proyecto desde cero, asegúrese de tener instalados:
- Compilador C++17 (GCC 7+, Clang 5+, MSVC 2017+)
- CMake 3.15 o superior
- Python 3.8 o superior
- Librerías de Python requeridas:
  ```bash
  pip install PySide6
  pip install psutil
  ```

## 3. Compilación del Backend (Motor de Simulación en C++)
El motor está ubicado en la carpeta `backend`. Para compilarlo:
```bash
cd backend
mkdir build && cd build
cmake ..
cmake --build .
```
Esto generará el ejecutable `simulator` (o `simulator.exe` en entornos Windows).

## 4. Ejecución del Backend (Uso Independiente por CLI)
Es posible ejecutar la simulación desde consola si se cuenta con un archivo JSON con los parámetros de entrada:
```bash
./simulator -i escenario_modelo.json -o output.json -t 200
```
**Parámetros de línea de comandos:**
- `-i <archivo>`: Archivo JSON de entrada (default: `escenario_modelo.json`)
- `-o <archivo>`: Archivo JSON de salida (default: `output.json`)
- `-t <ticks>`: Número máximo de ticks a simular (default: `200`)
- `-h`: Mostrar la ayuda

## 5. Ejecución Completa (Frontend)
Para ejecutar la interfaz gráfica y permitir que esta orqueste automáticamente las compilaciones y ejecuciones del C++:
```bash
cd frontend
python main.py
```
Se desplegará de inmediato la ventana principal y el diálogo de configuración del sistema.
