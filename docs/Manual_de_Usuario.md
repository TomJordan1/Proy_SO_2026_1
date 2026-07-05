# Manual de Usuario

Este manual explica cómo configurar y usar la interfaz gráfica (GUI) del simulador PatatOS.

## 1. Configuración Inicial
Al ejecutar la aplicación (mediante un doble clic en `iniciar_patatos.bat` o corriendo `python main.py`), aparecerá una ventana de configuración con cinco pestañas:
1. **CPU**: Permite elegir el número de núcleos, el algoritmo de planificación (FCFS, SJF, SRTF, RR, Prioridades, MLFQ), el quantum y el costo por cambio de contexto.
2. **Memoria**: Permite configurar el modelo de memoria del sistema:
   - **Modo Contiguo**: Define el tamaño de la RAM, reservas del SO y estrategia de asignación (First Fit, Best Fit, Worst Fit).
   - **Modo Paginado (Memoria Virtual)**: Si se habilita esta casilla, la memoria se divide en páginas de 4KB. Podrás configurar el tipo de Tabla de Páginas (Simple, Dos Niveles, Inversa, Hashed), elegir entre 9 algoritmos de reemplazo de páginas (ej. LRU, Clock, NRU), definir el tamaño de la memoria secundaria (Swap en HDD/SSD) y establecer la cantidad de entradas de la caché TLB.
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
- **Exportar Reporte**: Genera un documento PDF académico con métricas comparativas del rendimiento de los algoritmos de CPU y estrategias de memoria ejecutando la configuración actual en modo automático (batch).

## 3. Interfaz Principal (Pestañas)
La pantalla principal se divide en cuatro pestañas especializadas para facilitar la lectura de la información:

1. **Gestión de Procesos**:
   - **CPU Cores**: Muestra el estado de cada núcleo (IDLE, RUNNING o SWITCHING), el proceso en ejecución, el progreso del quantum y el valor del Program Counter (PC).
   - **Tabla PCB**: Tabla con los datos del Bloque de Control de Proceso de todos los programas.

2. **Gestión de Memoria**:
   - **Mapa de Memoria (RAM y Swap)**: Gráfico que representa el uso de la memoria física. Si el modo paginado está activo, verás una cuadrícula de Marcos (Frames) de 4KB y un visor adicional del almacenamiento Swap.
   - **Lupa de Memoria Virtual**: En modo paginado, podrás hacer clic en el ícono de inspección de memoria para ver en tiempo real el contenido de la TLB, la Tabla de Páginas de cada proceso y el uso detallado del Swap.

3. **Gestión de E/S y Rendimiento**:
   - **Colas de Listos y Bloqueados**: Muestra los procesos en espera por procesador o por periféricos.
   - **Dispositivos E/S**: Muestra el estado de cada periférico simulado. Incluye botones interactivos para confirmar o cancelar acciones cuando un dispositivo requiere intervención (como el teclado).
   - **Métricas**: Indicadores numéricos sobre el rendimiento de la CPU, tiempos de espera, fragmentación, fallos de página y hits en TLB.

4. **Línea de Tiempo y Registros**:
   - **Timeline (Gantt)**: Un diagrama que muestra el uso histórico de los núcleos en el tiempo.
   - **Consola de Registro**: Historial de eventos y logs emitidos por la simulación.
