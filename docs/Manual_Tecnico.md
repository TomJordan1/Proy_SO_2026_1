# Manual Técnico y Estructura

Este manual presenta la estructura de los directorios del código fuente y explica el propósito de los componentes internos del motor C++ (Backend).

## 1. Estructura del Código Fuente

### Backend (C++)
```text
backend/
├── CMakeLists.txt                 # Configuración de compilación
├── include/
│   └── nlohmann/                  # Librería externa JSON (header-only)
└── src/
    ├── main.cpp                   # Punto de entrada
    ├── simulator.hpp/.cpp         # Bucle y control principal
    ├── scheduler.hpp/.cpp         # Planificador de la CPU (6 algoritmos)
    ├── dispatcher.hpp/.cpp        # Cambio de contexto y asignación
    ├── memory_manager.hpp/.cpp    # Gestor de memoria contigua (Segmentación)
    ├── paged_memory_manager.hpp/.cpp # Gestor de Memoria Virtual (Paginación)
    ├── paged_memory.hpp/.cpp      # Estructuras de Marcos, Swap y TLB
    ├── page_table.hpp/.cpp        # Tablas de Páginas (Simple, 2 Niveles, Inversa, Hashed)
    ├── page_replacer.hpp/.cpp     # Algoritmos de Reemplazo (LRU, FIFO, Clock, etc.)
    ├── io_manager.hpp/.cpp        # Gestor de dispositivos y operaciones E/S
    ├── error_manager.hpp/.cpp     # Generador de errores
    ├── json_reader.hpp/.cpp       # Lector del archivo de configuración
    ├── json_writer.hpp/.cpp       # Generador de los fotogramas de salida
    ├── pcb.hpp                    # Bloque de Control de Proceso
    └── types.hpp                  # Enumeradores y tipos de datos base
```

### Script de Utilidad
```text
compilar_backend.bat               # Script para Windows que automatiza la compilación C++23 del backend
run_benchmark.py                   # Herramienta para simulaciones en bloque ("headless")
```

### Frontend (Python/Qt)
```text
frontend/
├── main.py                        # Punto de entrada principal
├── simulation/
│   ├── clock.py                   # Reloj de la simulación (QTimer)
│   ├── config.py                  # Estructuras de datos de hardware
│   └── paths.py                   # Rutas de los archivos JSON
└── ui/
    ├── styles.py                  # Tema visual oscuro
    ├── config_dialog.py           # Ventana de configuración inicial
    ├── main_window.py             # Ventana principal del reproductor
    └── widgets/                   # Componentes de la interfaz
        ├── cpu_widget.py          # Interfaz de los núcleos
        ├── memory_widget.py       # Gráfico de uso de memoria RAM y Swap
        ├── io_widget.py           # Paneles de estado de los periféricos
        ├── queue_widget.py        # Listas de procesos listos y bloqueados
        ├── pcb_table.py           # Tabla de procesos
        ├── pcb_detail_dialog.py   # Ventana con diagrama de estados
        ├── metrics_widget.py      # Barras e indicadores de rendimiento
        ├── timeline_widget.py     # Diagrama de Gantt
        ├── gantt_widget.py        # Módulo auxiliar para renderizado del Gantt
        └── log_widget.py          # Consola de registro
```

## 2. Funciones y Componentes del Backend

### Componente `Simulator`
| Función | Descripción |
| :--- | :--- |
| `run()` | Ejecuta el bucle principal de la simulación. Se detiene si hay un evento interactivo de E/S pendiente o para resolver un Page Fault. |
| `admitNewProcesses()` | Revisa y admite los procesos que llegan en el tick actual. |
| `processIOCompletions()` | Comprueba si alguna operación de E/S ha finalizado. |
| `dispatchCPUs()` | Asigna los núcleos de CPU a los procesos. |
| `executeOneCPUTick()` | Ejecuta un tick en los procesos que están en los núcleos. |
| `checkErrors()` | Determina si ocurre un error en el tick actual basado en la probabilidad configurada. |
| `terminateProcess()` | Libera la memoria y recursos de un proceso que ha finalizado. |
| `buildSnapshot()` | Genera una copia del estado actual para que sea guardada por JSON_writer. |

### Componentes de Memoria Virtual (MMU y Paginación)
| Función | Descripción |
| :--- | :--- |
| `allocate()` | En modo paginado, distribuye el proceso en múltiples páginas de 4KB y le asigna entradas en su respectiva Tabla de Páginas. |
| `translateAddress()` | Orquesta la traducción de direcciones virtuales. Consulta primero la TLB; si falla, consulta la Tabla de Páginas en RAM. |
| `handlePageFault()` | Administra la falta de una página en RAM. Envía el proceso a estado `BLOCKED_PAGEFAULT`, simula la latencia de traer la página del Swap y actualiza las tablas al finalizar. |
| `selectVictimPage()` | Utiliza el algoritmo de reemplazo seleccionado (ej. Clock, LRU, NRU) para desalojar una página al Swap si la RAM física está llena. |

### Componente `Scheduler`
| Función | Descripción |
| :--- | :--- |
| `selectNext()` | Selecciona el siguiente proceso a ejecutar según el algoritmo configurado. |
| `admit()` | Agrega un nuevo proceso a la cola de listos. |
| `requeue()` | Vuelve a poner en cola un proceso que perdió la CPU. |
| `applyAging()` | Incrementa la prioridad de los procesos si la opción de envejecimiento está activa. |

### Componente `Dispatcher`
| Función | Descripción |
| :--- | :--- |
| `contextSwitch()` | Intercambia el estado entre el proceso saliente y el entrante. |
| `tick()` | Reduce el contador asociado al tiempo de overhead del cambio de contexto. |

### Componente `IOManager`
| Función | Descripción |
| :--- | :--- |
| `requestIO()` | Crea una solicitud de E/S en un dispositivo determinado. |
| `cancelIO()` | Interrumpe la operación actual en un dispositivo. |
| `resolveIO()` | Marca una operación interactiva como resuelta, permitiendo que la simulación continúe. |
| `tick()` | Reduce el tiempo restante de las operaciones de E/S activas. |
| `randomInterrupt()` | Genera una operación asíncrona en procesos limitados por E/S. |

## 3. Herramientas de Pruebas y Benchmarking

El repositorio incluye el script `run_benchmark.py` ubicado en la raíz. Su objetivo es ejecutar simulaciones de manera automatizada ("headless" o sin interfaz gráfica) para obtener métricas comparativas entre los distintos algoritmos de CPU y estrategias de memoria. 

Al invocarlo:
1. Sobreescribe temporalmente el archivo `shared_data/input.json` con diferentes configuraciones de planificadores (FCFS, SJF, SRTF, RR, Priority) y de gestión de memoria (FIRST_FIT, BEST_FIT, WORST_FIT).
2. Limpia los eventos interactivos (como los de teclado) para evitar pausas. En el código fuente del motor de simulación (`simulator.cpp`) se omite la interrupción interactiva.
3. Extrae directamente del `output.json` los indicadores finales (Uso de CPU, tiempo de espera, respuesta, fragmentación máxima, etc.) y los imprime en consola en formato tabular.
