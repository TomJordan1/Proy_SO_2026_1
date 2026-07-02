# Manual de Usuario

Este manual explica cómo configurar y usar la interfaz gráfica (GUI) del simulador PatatOS.

## 1. Configuración Inicial
Al ejecutar la aplicación (`python main.py`), aparecerá una ventana de configuración con cinco pestañas:
1. **CPU**: Permite elegir el número de núcleos, el algoritmo de planificación (FCFS, SJF, SRTF, RR, Prioridades, MLFQ), el quantum y el costo por cambio de contexto.
2. **Memoria**: Permite definir el tamaño total de la memoria RAM, el espacio reservado para el SO, el tamaño mínimo del segmento y la estrategia de asignación (First Fit, Best Fit, Worst Fit).
3. **Dispositivos**: Permite ajustar la latencia (en ticks) de cada dispositivo de E/S.
4. **Simulación**: Permite configurar la velocidad de reproducción, la probabilidad de errores, el multiplicador de E/S y el envejecimiento (aging).
5. **Procesos**: Permite añadir procesos manualmente o importar los procesos reales en ejecución usando `psutil`.

## 2. Controles de la Simulación
La barra superior de la ventana principal incluye los siguientes controles:
- ▶ **(Iniciar)**: Inicia o reanuda la simulación.
- ⏸ **(Pausar)**: Detiene el avance automático de la simulación.
- ↺ **(Reset)**: Reinicia la simulación desde el tick 0.
- **Algoritmo**: Permite cambiar el algoritmo de planificación durante la ejecución.
- **Q (Quantum)**: Campo para modificar el tamaño del quantum.
- **Vel (Velocidad)**: Menú para ajustar la velocidad de la animación (Lento: 2s, Normal: 500ms, Rápido: 200ms, Turbo: 80ms).
- **Mem (Memoria)**: Selector para cambiar la estrategia de asignación de memoria.

## 3. Interfaz Principal
La pantalla principal se divide en varias áreas:
- **CPU Cores**: Muestra el estado de cada núcleo (IDLE, RUNNING o SWITCHING), el proceso en ejecución, el progreso del quantum y el valor del Program Counter (PC).
- **Colas de Listos**: Muestra los procesos en estado de listos, asignados a cada núcleo.
- **Cola de Bloqueados**: Muestra los procesos que están esperando por E/S.
- **Tabla PCB**: Tabla con los datos del Bloque de Control de Proceso de todos los programas.
- **Mapa de Memoria**: Gráfico que representa el uso y los segmentos de la RAM.
- **Dispositivos E/S**: Muestra el estado y progreso de cada periférico simulado. Incluye botones interactivos para confirmar o cancelar acciones cuando un dispositivo requiere intervención (como el teclado).
- **Métricas**: Indicadores numéricos sobre el rendimiento de la CPU, tiempos de espera y respuestas.
- **Timeline**: Un Diagrama de Gantt que muestra el uso de los núcleos en el tiempo.
