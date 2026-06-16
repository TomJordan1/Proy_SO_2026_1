# Guía de Integración Backend (C++) / Frontend (Python) - v4

Esta guía detalla la estructura esperada para el archivo `output_modelo.json` que genera el motor de C++. El frontend (escrito en Python) consume este archivo para animar la simulación de manera automática.

## 🏗 Arquitectura y Flujo

1. **Pre-cálculo**: El backend en **C++** se encarga de toda la lógica pesada. Al iniciar o ante un cambio, lee `escenario_modelo.json` y simula todos los procesos de inicio a fin de un tirón. El resultado de cada instante de tiempo (tick) se guarda como un "fotograma" dentro de `output_modelo.json`.
2. **Reproducción en caliente**: Python carga `output_modelo.json` y reproduce la simulación avanzando tick por tick.
3. **Cambios de configuración en caliente**: Si el usuario cambia el algoritmo (ej. FCFS a Round Robin) o añade un proceso desde la interfaz, Python guarda esos cambios en `escenario_modelo.json` y vuelve a ejecutar el motor C++. El backend lee el nuevo estado, recalcula todo el futuro y sobreescribe `output_modelo.json`. La interfaz recarga el archivo y retoma la reproducción sin que el usuario note el salto.
4. **Interacciones (E/S)**: Si ocurre una interrupción que requiere interacción del usuario (ej. Teclado), Python pausa la animación, pide la decisión al usuario y agrega el evento al `escenario_modelo.json` (lista `"events"`). Acto seguido, dispara al C++ de nuevo para recalcular el futuro bajo la nueva decisión.

---

## 📄 Estructura Principal del JSON

El archivo JSON de salida debe contener un objeto principal con una lista de `ticks`.

```json
{
  "ticks": [
    { /* Fotograma del tick 0 */ },
    { /* Fotograma del tick 1 */ },
    { /* Fotograma del tick 2 */ }
  ]
}
```

---

## 🔎 Estructura de cada Fotograma (`tick`)

Cada elemento dentro de `ticks` representa el estado completo del sistema operativo en ese instante de tiempo:

```json
{
  "tick": 47,
  "metrics": { ... },
  "cores": [ ... ],
  "process_table": [ ... ],
  "ready_queues": [ ... ],
  "waiting": [ ... ],
  "io_devices": [ ... ],
  "memory": { ... },
  "console_logs": [ ... ]
}
```



---

### 1. Bitácora del Sistema (`console_logs`)

El motor de C++ es el encargado de proveer los mensajes precisos de lo que ocurre en las entrañas del planificador en cada tick. El frontend simplemente imprime esta lista. La notación estándar obligatoria es prefijar todo con `[T=N]`.

```json
"console_logs": [
  "[T=47] ADMIT P1 (python.exe)",
  "[T=47] [CTX SWITCH] CPU0 -> Entra P1",
  "[T=50] QUANTUM_EXP P1 (python.exe)",
  "[T=50] [CTX SWITCH] CPU0 -> Sale P1"
]
```

### 2. Tabla de Procesos (`process_table`)

Esta sección se usa para dibujar el "Inspector de PCB". El C++ calcula todas las métricas de tiempo y progreso.

```json
"process_table": [
  {
    "pid": 3,
    "name": "proc",
    "state": "RUNNING",              // NEW, READY, RUNNING, WAITING, TERMINATED, ERROR
    "type": "CPU_BOUND",             // SYSTEM, INTERACTIVE, CPU_BOUND, I/O_BOUND
    "priority": 5,                   // Rango 0-9 (0 es más alta, 9 más baja)
    "burst_time": 20,
    "remaining_time": 15,            // Tiempo que le falta en CPU
    "waiting_time": 5,               // Ticks que ha pasado en la cola de listos
    "arrival_tick": 0,               // Tick en el que se creó
    "response_time": 2,              // Ticks desde arrival_tick hasta su primer RUNNING
    "finish_time": null,             // Tick donde terminó
    "turnaround_time": 0,            // Tiempo total (finish_time - arrival_tick)
    "completion_percent": 25.0,      // Progreso general
    
    "pc": 1024,                      // Program Counter numérico
    "pc_hex": "0x0400",              // Program Counter en hexadecimal
    
    "registers": {
      "AX": 0, "BX": 42, "CX": 1, "DX": 0
    }
  }
]
```

---

### 3. Dispositivos E/S (`io_devices`)

Se utiliza para dibujar las barras de progreso del hardware externo.

```json
"io_devices": [
  {
    "name": "KEYBOARD",
    "status": "BUSY",
    "queue_length": 1,
    "current_pid": 14,
    "current_name": "python.exe",
    "progress_percent": 42.0
  }
]
```

---

### 4. Cambios de configuración (El archivo de entrada)

El frontend inyecta la configuración seleccionada por el usuario en `escenario_modelo.json` usando las siguientes llaves exactas. El backend de C++ debe leer de ahí.

```json
"hardware": {
  "cpu": {
    "scheduler": "RR",       // Puede ser "FCFS", "SJF", "RR", o "Priority"
    "quantum": 4,            // Valor del quantum numérico
    "preemptive": true       // true para algoritmos expropiativos
  },
  "memory": {
    "allocationStrategy": "FIRST_FIT"  // "FIRST_FIT", "BEST_FIT", "WORST_FIT"
  }
}
```

---

### 5. Memoria y Paginación (`memory`)

Este bloque es vital para el mapa de RAM visual en el frontend. El mapa usa `stats` para calcular los porcentajes de fragmentación generales.

```json
"memory": {
  "blocks": [
    {
      "start_address": 0,
      "size": 64,
      "is_free": false,
      "process_id": null,
      "segment_type": "OS",
      "label": "SO"
    }
  ],
  "stats": {
    "total_mb": 1024,
    "used_mb": 192,
    "free_mb": 832,
    "fragmentation": 12.5,
    "strategy": "FIRST_FIT"
  }
}
```

---

### 6. Métricas de Rendimiento (`metrics`)

*Nota para el equipo C++: El frontend ahora lee el `throughput` en su valor crudo (procesos terminados / tiempo transcurrido) y se encarga de escalarlo y formatearlo matemáticamente para el usuario final.*

```json
"metrics": {
  "cpu_utilization": 80.5,
  "throughput": 1.2,
  "avg_turnaround": 34.0,
  "avg_waiting": 12.0,
  "avg_response": 4.5,
  "context_switches": 25,
  "starvation_events": 0,
  "total_errors": 1
}
```

### 7. Núcleos y Colas (`cores` y `ready_queues`)

```json
"cores": [
  {
    "id": 0,
    "is_busy": true,
    "is_switching": false,
    "process": { /* Objeto PCB resumido del proceso actual */ }
  }
]
```

```json
"ready_queues": [
  [
    {
      "pid": 5,
      "name": "brave.exe",
      "priority": 5,
      "waiting_time": 47
    }
  ]
]
```
