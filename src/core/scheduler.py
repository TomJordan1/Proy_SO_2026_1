"""
core/scheduler.py — Algoritmos de planificación de CPU.

El scheduler decide qué proceso de la cola READY ejecutará la CPU.
Implementa el PATRÓN STRATEGY: cada algoritmo es una clase separada
que hereda de BaseScheduler. El engine solo conoce la interfaz base.

Ventaja del patrón Strategy:
  - Cambiar algoritmo en runtime sin modificar el engine
  - Agregar nuevos algoritmos sin modificar los existentes
  - Facilita comparar algoritmos (el engine usa la misma interfaz)

Algoritmos implementados:

  1. FCFS (First Come First Served):
     ┌───────────────────────────────────────────────────────┐
     │ Cola: [P1, P2, P3, P4]                                │
     │ CPU ejecuta P1 hasta que termine (no apropiativo)     │
     │ Luego P2, luego P3, etc.                             │
     └───────────────────────────────────────────────────────┘
     + Simple, predecible
     - Convoy effect: P2 espera aunque sea corto

  2. Round Robin (RR):
     ┌───────────────────────────────────────────────────────┐
     │ Cola: [P1, P2, P3] con quantum=3                      │
     │ P1 ejecuta 3 ticks → al final de la cola             │
     │ P2 ejecuta 3 ticks → al final de la cola             │
     │ P3 ejecuta 3 ticks → al final de la cola             │
     │ P1 ejecuta 3 ticks más, ... así hasta terminar        │
     └───────────────────────────────────────────────────────┘
     + Equitativo, buena respuesta interactiva
     - Más context switches = más overhead
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .models import PCB


# ─────────────────────────────────────────────────────────────────────────────
# Interfaz base (Strategy)
# ─────────────────────────────────────────────────────────────────────────────

class BaseScheduler(ABC):
    """
    Interfaz base para todos los algoritmos de planificación.

    El Engine trabaja SOLO con esta interfaz (patrón Strategy).
    Las subclases implementan la lógica específica de cada algoritmo.
    """

    def __init__(self):
        # Cola de procesos READY. deque = Double-Ended Queue
        # Permite inserción/extracción eficiente O(1) en ambos extremos
        self.ready_queue: deque[PCB] = deque()

    def add(self, pcb: PCB) -> None:
        """Agrega un proceso a la cola READY."""
        self.ready_queue.append(pcb)

    @abstractmethod
    def next(self) -> Optional[PCB]:
        """
        Selecciona y extrae el siguiente proceso a ejecutar.

        Returns:
            El proceso seleccionado, o None si la cola está vacía.
        """
        pass

    def remove(self, pcb: PCB) -> None:
        """
        Elimina un proceso específico de la cola.
        (Ejemplo: proceso que pasa a WAITING)
        """
        try:
            self.ready_queue.remove(pcb)
        except ValueError:
            pass  # No estaba en la cola, ignorar

    def is_empty(self) -> bool:
        """True si no hay procesos esperando."""
        return len(self.ready_queue) == 0

    def snapshot(self) -> list[PCB]:
        """
        Retorna una COPIA de la cola para visualización.
        No modifica la cola original.
        """
        return list(self.ready_queue)

    def clear(self) -> None:
        """Vacía la cola."""
        self.ready_queue.clear()

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del algoritmo para mostrar en UI."""
        pass


# ─────────────────────────────────────────────────────────────────────────────
# FCFS — First Come First Served
# ─────────────────────────────────────────────────────────────────────────────

class FCFSScheduler(BaseScheduler):
    """
    FCFS: El proceso que llegó primero ejecuta primero.

    Características:
      - NO apropiativo: una vez en CPU, ejecuta hasta terminar
        (a menos que solicite I/O o ocurra un error)
      - Cola FIFO pura: popleft() es siempre O(1)
      - Simple de implementar y entender

    Problema conocido — Convoy Effect:
      Si P1 tiene burst_time=50 y llegan P2, P3 con burst_time=5,
      P2 y P3 esperarán 50 ticks aunque sean muy cortos.
      Compara esto con Round Robin donde P2 y P3 ejecutarían rápido.
    """

    def next(self) -> Optional[PCB]:
        """
        Selecciona el PRIMERO de la cola (FIFO).
        popleft() extrae del frente en O(1).
        """
        if self.ready_queue:
            return self.ready_queue.popleft()
        return None

    @property
    def name(self) -> str:
        return "FCFS"


# ─────────────────────────────────────────────────────────────────────────────
# Round Robin
# ─────────────────────────────────────────────────────────────────────────────

class RoundRobinScheduler(BaseScheduler):
    """
    Round Robin: cada proceso recibe un quantum de tiempo.

    Funcionamiento por tick:
      1. El proceso ejecuta 1 tick → quantum_used += 1
      2. Si quantum_used >= quantum:
         - Proceso va al FINAL de la cola (requeue)
         - Siguiente proceso toma la CPU
      3. Si el proceso termina antes del quantum:
         - CPU queda libre, siguiente proceso entra

    Efecto del tamaño del quantum:
      - Quantum muy pequeño (1): máximo overhead (context switch cada tick)
      - Quantum muy grande (∞): equivalente a FCFS
      - Recomendado: quantum ≈ tiempo_medio_de_ráfaga / 10

    En nuestro sistema: el ENGINE controla el quantum_used y llama
    a requeue() cuando expira. El scheduler solo administra la cola.
    """

    def __init__(self, quantum: int = 4):
        super().__init__()
        # Quantum configurable: número máximo de ticks por turno
        self.quantum: int = max(1, quantum)

    def next(self) -> Optional[PCB]:
        """
        Selecciona el siguiente proceso en rotación.
        El control del quantum ocurre en el engine, no aquí.
        """
        if self.ready_queue:
            return self.ready_queue.popleft()
        return None

    def requeue(self, pcb: PCB) -> None:
        """
        Re-encola un proceso al FINAL de la cola cuando su quantum expira.

        Esto garantiza la rotación: todos los procesos obtienen turnos
        de manera equitativa (fairness).
        """
        self.ready_queue.append(pcb)

    @property
    def name(self) -> str:
        return f"Round Robin (Q={self.quantum})"
