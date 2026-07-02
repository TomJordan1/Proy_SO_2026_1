# Flujo Global de Ejecución: PatatOS

Este documento describe de manera general cómo funciona el simulador PatatOS, explicando la interacción entre sus distintos módulos y el ciclo de la simulación.

## Arquitectura

PatatOS se divide en dos componentes principales (Frontend en Python y Backend en C++) que se comunican mediante archivos JSON.

```mermaid
graph LR
    A[Frontend Python<br/>Interfaz Gráfica] -- Escribe --> B(input.json<br/>Configuración y Eventos)
    B -- Lee --> C[Backend C++<br/>Motor de Simulación]
    C -- Escribe --> D(output.json<br/>Fotogramas de Simulación)
    D -- Lee y Anima --> A
```

---

## 1. Fase de Configuración (Frontend)

El proceso inicia cuando el usuario ejecuta la interfaz (`main.py`) y configura el entorno en la primera ventana.
- Se definen las características del hardware, memoria y E/S.
- Se definen los procesos (manualmente o importando los del sistema operativo host con `psutil`).
- Al hacer clic en "Generar", la interfaz de Python guarda esta información en `shared_data/input.json`.

---

## 2. Fase de Simulación (Backend)

Inmediatamente después de guardar el archivo, Python ejecuta como subproceso el motor compilado en C++ (`simulator.exe`).

- **Lectura:** C++ lee `input.json`.
- **Ejecución:** El motor simula internamente el progreso de todos los procesos desde el Tick 0, procesando la planificación de CPU y las operaciones de memoria y E/S. Se detiene automáticamente si requiere una decisión interactiva del usuario (por ejemplo, interacción de teclado).
- **Grabación:** Por cada tick simulado, el motor genera un registro del estado del procesador, de la memoria, de los dispositivos y las métricas.
- **Escritura:** Toda la información recolectada se guarda en `shared_data/output.json`. Luego, el proceso de C++ termina.

---

## 3. Fase de Reproducción y Animación (Frontend)

El control regresa a la interfaz gráfica de Python.
- Python lee el archivo `output.json`.
- Inicia un temporizador interno que se actualiza a la velocidad seleccionada por el usuario.
- En cada ciclo del temporizador, la interfaz avanza un fotograma leyendo la información generada y dibujando en pantalla el progreso de los procesos, el uso de memoria, las colas y los registros de consola.

---

## 4. Interactividad en Tiempo Real

El simulador permite introducir interacciones y cambios mientras la animación se está reproduciendo:
- **Eventos Interactivos (Teclado):** Cuando un dispositivo requiere confirmación del usuario, la interfaz detiene la animación y muestra botones de confirmación.
- **Cambio de Algoritmo o Memoria:** El usuario puede seleccionar un algoritmo diferente o estrategia de memoria desde los menús superiores.
- **Inyección de Procesos:** El usuario puede añadir nuevos procesos al hacer clic en "Añadir Proceso en Caliente".

**Manejo de interacciones:**
Al ocurrir cualquiera de estos eventos, Python añade un evento en el archivo `input.json` indicando el tick en que ocurrió la interacción. Seguidamente, vuelve a invocar a `simulator.exe`. El motor C++ lee el nuevo evento, recalcula la simulación a partir de ese tick (o retoma desde el inicio aplicando las nuevas reglas), y sobrescribe el archivo `output.json`. Python entonces recarga el archivo y retoma la animación de forma fluida.
