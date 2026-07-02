# Manual Técnico y Estructura

Este manual presenta la estructura de los directorios del código fuente y explica el propósito de los componentes internos del motor C++ (Backend).

## 1. Estructura del Código Fuente

### Backend (C++)
```text
backend/
├── CMakeLists.txt              # Configuración de compilación
├── include/
│   └── nlohmann/               # Librería externa JSON (header-only)
└── src/
    ├── main.cpp                # Punto de entrada
    ├── simulator.hpp/.cpp      # Bucle y control principal
    ├── scheduler.hpp/.cpp      # Planificador de la CPU (6 algoritmos)
    ├── dispatcher.hpp/.cpp     # Cambio de contexto y asignación
    ├── memory_manager.hpp/.cpp # Gestor de memoria RAM
    ├── io_manager.hpp/.cpp     # Gestor de dispositivos y operaciones E/S
    ├── error_manager.hpp/.cpp  # Generador de errores
    ├── json_reader.hpp/.cpp    # Lector del archivo de configuración
    ├── json_writer.hpp/.cpp    # Generador de los fotogramas de salida
    ├── pcb.hpp                 # Bloque de Control de Proceso
    └── types.hpp               # Enumeradores y tipos de datos base
```

### Frontend (Python/Qt)
```text
frontend/
├── main.py                     # Punto de entrada principal
├── simulation/
│   ├── clock.py                # Reloj de la simulación (QTimer)
│   ├── config.py               # Estructuras de datos de hardware
│   └── paths.py                # Rutas de los archivos JSON
└── ui/
    ├── styles.py               # Tema visual oscuro
    ├── config_dialog.py        # Ventana de configuración inicial
    ├── main_window.py          # Ventana principal del reproductor
    └── widgets/                # Componentes de la interfaz
        ├── cpu_widget.py       # Interfaz de los núcleos
        ├── memory_widget.py    # Gráfico de uso de memoria
        ├── io_widget.py        # Paneles de estado de los periféricos
        ├── queue_widget.py     # Listas de procesos listos y bloqueados
        ├── pcb_table.py        # Tabla de procesos
        ├── pcb_detail_dialog.py# Ventana con diagrama de estados
        ├── metrics_widget.py   # Barras e indicadores de rendimiento
        ├── timeline_widget.py  # Diagrama de Gantt
        └── log_widget.py       # Consola de registro
```

## 2. Funciones y Componentes del Backend

### Componente `Simulator`
| Función | Descripción |
| :--- | :--- |
| `run()` | Ejecuta el bucle principal de la simulación. Se detiene si hay un evento interactivo de E/S pendiente. |
| `admitNewProcesses()` | Revisa y admite los procesos que llegan en el tick actual. |
| `processIOCompletions()` | Comprueba si alguna operación de E/S ha finalizado. |
| `dispatchCPUs()` | Asigna los núcleos de CPU a los procesos. |
| `executeOneCPUTick()` | Ejecuta un tick en los procesos que están en los núcleos. |
| `checkErrors()` | Determina si ocurre un error en el tick actual basado en la probabilidad configurada. |
| `terminateProcess()` | Libera la memoria y recursos de un proceso que ha finalizado. |
| `buildSnapshot()` | Genera una copia del estado actual para que sea guardada por JSON_writer. |

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

### Componente `MemoryManager`
| Función | Descripción |
| :--- | :--- |
| `allocate()` | Asigna memoria a un proceso utilizando la estrategia configurada (First/Best/Worst Fit). |
| `free()` | Marca la memoria de un proceso como libre. |
| `findFreeBlock()` | Busca un bloque de memoria disponible según la estrategia. |
| `splitBlock()` | Divide un bloque libre si es mayor al tamaño necesario. |
| `mergeAdjacentFree()` | Une particiones de memoria contiguas que están libres. |
| `stats()` | Calcula estadísticas de uso y fragmentación de memoria. |

### Componente `IOManager`
| Función | Descripción |
| :--- | :--- |
| `requestIO()` | Crea una solicitud de E/S en un dispositivo determinado. |
| `cancelIO()` | Interrumpe la operación actual en un dispositivo. |
| `resolveIO()` | Marca una operación interactiva como resuelta, permitiendo que la simulación continúe. |
| `tick()` | Reduce el tiempo restante de las operaciones de E/S activas. |
| `randomInterrupt()` | Genera una operación asíncrona en procesos limitados por E/S. |

### Componente `ErrorManager`
| Función | Descripción |
| :--- | :--- |
| `tryInjectError()` | Evalúa de manera aleatoria si se produce un error en el sistema. |
| `errorRate()` | Devuelve el total de errores acumulados. |
