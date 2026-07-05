# PatatOS - Simulador de Sistema Operativo
![C++](https://img.shields.io/badge/c++-%2300599C.svg?style=for-the-badge&logo=c%2B%2B&logoColor=white) ![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

<p align="center">
  <img src="example.gif" width="750" alt="Ejemplo de uso">
</p>

## 👥 Integrantes

* Candia Usca, Zhaid Genaro - 20241096K
* Morales Quispe, Rodrigo - 20241215J
* Pérez López, Tom Jordan - 20240376J
* Reyes Campos, Ricardo Gaspar - 20244014E 


## 📂 Estructura del Repositorio

```text
Proy_SO_2026_1/
├── .gitignore                   # Archivos y carpetas ignorados por Git
├── README.md                    # Documentación principal del proyecto
├── backend/                     # Motor de la lógica interna hecho en C++
├── docs/                        # Documentación adicional, informes o manuales del proyecto
├── frontend/                    # Constructor del input y del GUI hecho en Python
├── iniciar_patatos.bat          # Lanzador automático (instala dependencias y compila si es necesario)
└── shared_data/                 # Archivos input.json y output.json que unen el frontend y el backend
```

```text
backend/
├── CMakeLists.txt               # Configuración de compilación
├── include/
│   └── nlohmann/                # Librería JSON (header-only)
└── src/
    ├── main.cpp                 # Punto de entrada
    ├── simulator.hpp/.cpp       # Orquestador principal
    ├── scheduler.hpp/.cpp       # Planificador (6 algoritmos)
    ├── dispatcher.hpp/.cpp      # Despachador (cambio de contexto)
    ├── memory_manager.hpp/.cpp  # Gestor de memoria contigua
    ├── paged_memory_manager.hpp/.cpp # Gestor de memoria paginada
    ├── paged_memory.hpp/.cpp    # Memoria virtual y Swap
    ├── page_table.hpp/.cpp      # Tablas de páginas y TLB
    ├── page_replacer.hpp/.cpp   # Algoritmos de reemplazo de páginas
    ├── io_manager.hpp/.cpp      # Gestor de E/S
    ├── error_manager.hpp/.cpp   # Inyección de errores
    ├── json_reader.hpp/.cpp     # Parser de entrada JSON
    ├── json_writer.hpp/.cpp     # Generador de salida JSON
    ├── pcb.hpp                  # Estructura del PCB
    └── types.hpp                # Tipos, enums y configuración
```

```text
frontend/
├── main.py                      # Punto de entrada
├── simulation/
│   ├── clock.py                 # Reloj de simulación (QTimer)
│   ├── config.py                # Configuración de hardware
│   └── paths.py                 # Resolutor de rutas relativas absolutas
└── ui/
    ├── styles.py                # Tema visual oscuro (QSS)
    ├── config_dialog.py         # Diálogo de configuración (5 pestañas)
    ├── main_window.py           # Ventana principal y generador de reportes PDF
    └── widgets/
        ├── cpu_widget.py        # Panel de núcleos CPU
        ├── memory_widget.py     # Mapa visual de memoria
        ├── io_widget.py         # Panel de dispositivos E/S
        ├── queue_widget.py      # Colas de listos y bloqueados
        ├── pcb_table.py         # Tabla de procesos
        ├── pcb_detail_dialog.py # Diagrama de 5 estados animado
        ├── metrics_widget.py    # Métricas de rendimiento
        ├── timeline_widget.py   # Diagrama de Gantt clásico
        ├── gantt_widget.py      # Diagrama de Gantt optimizado
        └── log_widget.py        # Log de consola
```
