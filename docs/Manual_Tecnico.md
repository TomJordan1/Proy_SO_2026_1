# Manual Técnico y Estructura

Este manual presenta la estructura de los directorios del código fuente y explica la responsabilidad de las funciones internas del motor C++ (Backend).

## 1. Estructura del Código Fuente

### Backend (C++)
```text
backend/
├── CMakeLists.txt              # Configuración de compilación
├── include/
│   └── nlohmann/               # Librería externa JSON (header-only)
└── src/
    ├── main.cpp                # Punto de entrada
    ├── simulator.hpp/.cpp      # Orquestador principal
    ├── scheduler.hpp/.cpp      # Planificador de la CPU (6 algoritmos)
    ├── dispatcher.hpp/.cpp     # Despachador (manejo y cambio de contexto)
    ├── memory_manager.hpp/.cpp # Gestor de memoria RAM
    ├── io_manager.hpp/.cpp     # Gestor de E/S y dispositivos
    ├── error_manager.hpp/.cpp  # Módulo de inyección aleatoria de errores
    ├── json_reader.hpp/.cpp    # Parser para cargar la configuración
    ├── json_writer.hpp/.cpp    # Generador de fotogramas para exportar JSON
    ├── pcb.hpp                 # Struct del Bloque de Control del Proceso (PCB)
    └── types.hpp               # Enumeradores de estado, configuraciones y tipos
```

### Frontend (Python/Qt)
```text
frontend/
├── main.py                     # Punto de entrada principal
├── simulation/
│   ├── clock.py                # Reloj maestro de simulación (vía QTimer)
│   ├── config.py               # DTO para las variables de hardware
│   └── paths.py                # Ubicación centralizada de archivos JSON
└── ui/
    ├── styles.py               # Tema visual y hojas de estilo oscuro (QSS)
    ├── config_dialog.py        # Interfaz de las 5 pestañas de configuración
    ├── main_window.py          # Ventana principal del reproductor
    └── widgets/                # Distintos componentes para armar la ventana
        ├── cpu_widget.py       # Interfaz gráfica de los núcleos de CPU
        ├── memory_widget.py    # Generación de la gráfica de particiones de memoria
        ├── io_widget.py        # Generación de tarjetas para dispositivos
        ├── queue_widget.py     # Tarjetas animadas de procesos listos/bloqueados
        ├── pcb_table.py        # Grilla para los registros
        ├── pcb_detail_dialog.py# Animación especial en ventana para diagrama de 5 estados
        ├── metrics_widget.py   # Datos procesados con barras de progreso
        ├── timeline_widget.py  # Construcción del diagrama de Gantt
        └── log_widget.py       # Visor de la consola y bitácora
```

## 2. Funciones y Componentes del Backend

### Componente `Simulator`
| Función | Descripción |
| :--- | :--- |
| `run()` | Ejecuta el bucle principal de la simulación *tick a tick*. Realiza paradas automáticas cuando surge la necesidad de consultar al usuario por I/O. |
| `admitNewProcesses()` | Revisa y admite la carga de aquellos procesos que alcanzan su *tick* de arribo. |
| `processIOCompletions()` | Comprueba y avisa si alguna operación pendiente de E/S finalizó con éxito en la presente etapa. |
| `dispatchCPUs()` | Asigna inteligentemente las CPUs evaluando una posible expropiación (preempt) y gestionando el overhead. |
| `executeOneCPUTick()` | Llama para ejecutar exactamente un tick de CPU en los procesos que actualmente residen en los núcleos. |
| `checkErrors()` | Valida de manera aleatoria si en el tick en curso surge un error artificial. |
| `terminateProcess()` | Realiza de forma limpia la liberación de todos los recursos y memorias de un PCB moribundo. |
| `buildSnapshot()` | Genera la foto congelada (*snapshot*) de las métricas en un segundo exacto para delegarlo al JSON_writer. |

### Componente `Scheduler`
| Función | Descripción |
| :--- | :--- |
| `selectNext()` | Aplica estrictamente las políticas correspondientes de ordenación y selecciona un candidato apto. |
| `admit()` | Desplaza o inserta un nuevo programa que ha sido validado para entrar de inmediato a su respectiva cola de listos. |
| `requeue()` | Agrega nuevamente un proceso que padeció una expropiación (por ej. si está en MLFQ, probablemente lo degrada de nivel). |
| `applyAging()` | Recorre la cola y aplica un envejecimiento sistemático si la política lo dictamina para evitar inanición. |

### Componente `Dispatcher`
| Función | Descripción |
| :--- | :--- |
| `contextSwitch()` | Toma todos los registros actuales y los empaca cuidadosamente en el PCB del proceso saliente, haciendo la inversa en el proceso entrante. |
| `tick()` | Decrementa únicamente el contador relacionado al Overhead estipulado para evitar arranques antes de tiempo. |

### Componente `MemoryManager`
| Función | Descripción |
| :--- | :--- |
| `allocate()` | Se encarga de parcelar y distribuir una porción libre de RAM al proceso utilizando un particionamiento por segmentos pre-calculados (First/Best/Worst Fit). |
| `free()` | Encuentra de inmediato las celdas utilizadas y las desmarca como ocupadas. |
| `findFreeBlock()` | Herramienta de búsqueda interna iterativa basada estrictamente en la estrategia global requerida en el constructor de este componente. |
| `splitBlock()` | Segmenta una pieza libre mayor de acuerdo a un corte matemático exacto para evitar desperdicio y generar particiones. |
| `mergeAdjacentFree()` | Escanea en tiempo real los contornos en búsqueda de huecos unidos para sumarlos y aliviar el nivel de fragmentación externa. |
| `stats()` | Condensa las matemáticas e informa el ratio global del uso de la placa y su fragmentación. |

### Componente `IOManager`
| Función | Descripción |
| :--- | :--- |
| `requestIO()` | Encola una solicitud de un dispositivo específico según latencia preestablecida en la configuración inicial. |
| `cancelIO()` | Interrumpe intempestivamente la operación actual en el procesador I/O; empleado durante señales del teclado con un *abort*. |
| `tick()` | Reduce los relojes internos de espera estricta de hardware de manera global. |
| `randomInterrupt()` | Forja un evento asíncrono para interrumpir la paz de un IO_BOUND con el fin de generar E/S de manera independiente. |

### Componente `ErrorManager`
| Función | Descripción |
| :--- | :--- |
| `tryInjectError()` | Decide, a través del motor numérico estocástico, si es propicio lanzar un pánico en el tick. |
| `errorRate()` | Devuelve el total acumulado de las tasas que hayan generado estragos para alimentar los análisis de UI en vivo. |
