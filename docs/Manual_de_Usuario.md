# Manual de Usuario

Este manual orienta al usuario final sobre cómo configurar e interactuar con la simulación del Sistema Operativo PatatOS mediante la interfaz gráfica (GUI).

## 1. Configuración Inicial
Al arrancar la aplicación (`python main.py`), se presentará un diálogo con cinco pestañas que permiten personalizar la arquitectura antes de iniciar la simulación:
1. **CPU**: Selecciona el número de núcleos, el algoritmo de planificación (FCFS, SJF, SRTF, RR, Prioridades, MLFQ), el quantum y el costo de cambio de contexto (overhead).
2. **Memoria**: Define el tamaño total de la memoria RAM, cuánto se reserva para el SO, el tamaño base del segmento, y la estrategia de asignación (First Fit, Best Fit, Worst Fit).
3. **Dispositivos**: Permite configurar y alterar la latencia (en *ticks*) de cada dispositivo simulado de E/S.
4. **Simulación**: Establece la velocidad de reproducción, la probabilidad de fallos (error), el multiplicador general de E/S, y si está activo el envejecimiento (*aging*).
5. **Procesos**: Puedes crear procesos de manera estática y manual, o inyectar los procesos actuales reales del sistema operativo utilizando `psutil`.

## 2. Controles de la Simulación
En la ventana principal de simulación, la barra superior dispone de controles en tiempo real:
- ▶ **(Play / Iniciar)**: Arranca o reanuda el reloj de la simulación.
- ⏸ **(Pausa)**: Detiene el reloj de la simulación momentáneamente.
- ↺ **(Reset)**: Limpia el progreso y vuelve el tiempo (reloj) al tick inicial 0.
- **Algoritmo**: Selector dinámico para cambiar el algoritmo de planificación "en caliente", lo cual recalcula automáticamente los eventos futuros.
- **Q (Quantum)**: Campo de texto para modificar el tamaño del quantum de manera inmediata.
- **Vel (Velocidad)**: Un menú desplegable para controlar la velocidad de animación (Lento: 2s, Normal: 500ms, Rápido: 200ms, Turbo: 80ms por cada *tick*).
- **Mem (Memoria)**: Selector de estrategia de asignación de bloques libres para cambios en tiempo real.

## 3. Visualización del Sistema
La pantalla de visualización principal está dividida en ocho áreas para observar en detalle lo que sucede en el motor:
- **CPU Cores**: Observa el estado actual de cada núcleo físico del procesador (IDLE, RUNNING o SWITCHING), el proceso atado, una barra de progreso que llena el quantum, y un panel que muestra el Program Counter (PC) junto con los registros internos.
- **Colas de Listos**: Los procesos que esperan por la CPU, organizados eficientemente de acuerdo a su núcleo.
- **Cola de Bloqueados**: Listado de los procesos que han solicitado I/O y esperan ser liberados.
- **Tabla PCB**: Tabla integral y ordenable con todos los campos del Bloque de Control de Proceso para cada uno de los programas.
- **Mapa de Memoria**: Representación visual de cómo están repartidos físicamente los diferentes segmentos en la RAM.
- **Dispositivos E/S**: El progreso y estado (libre u ocupado) de cada dispositivo.
- **Métricas**: Estadísticas en tiempo real basadas en ocho indicadores de rendimiento que se diferencian mediante código de colores.
- **Timeline (Línea de Tiempo)**: Un Diagrama de Gantt automatizado que te permite ver con claridad la actividad asignada a cada núcleo del procesador con el paso de los ticks.
