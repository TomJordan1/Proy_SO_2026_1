"""
kernel/scheduler/base.py — Interfaz base para todos los schedulers.

Patrón Strategy: cada algoritmo de planificación es una subclase
de BaseScheduler. El engine solo conoce esta interfaz.

Schedulers implementados:
    FCFSScheduler     — First Come, First Served (no apropiativo)
    SJFScheduler      — Shortest Job First (no apropiativo)
    SRTFScheduler     — Shortest Remaining Time First (apropiativo)
    PriorityScheduler — Prioridad (apropiativo y no apropiativo)
    RoundRobinScheduler — Round Robin con quantum configurable
    MLFQScheduler     — Multilevel Feedback Queue (STUB — futura integración)

El engine mantiene UNA lista de schedulers (uno por CPU core).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models.pcb import PCB, ProcessState


class BaseScheduler(ABC):
    """
    Interfaz del planificador de procesos.

    Cada implementación mantiene su propia cola de READY.
    El engine llama a `select_next()` cuando un CPU core está libre.
    """

    def __init__(self) -> None:
        self.ready_queue: List[PCB] = []
        """Cola de procesos listos para ejecutar."""

        self.context_switch_count: int = 0
        """Total de cambios de contexto realizados por este scheduler."""

    # ── API del scheduler ─────────────────────────────────────────────────────

    def add_process(self, pcb: PCB) -> None:
        """
        Agrega un proceso a la cola READY.
        Las subclases pueden sobreescribir para reordenar la cola.
        """
        pcb.state = ProcessState.READY
        self.ready_queue.append(pcb)

    @abstractmethod
    def select_next(self, current_tick: int) -> Optional[PCB]:
        """
        Selecciona el próximo proceso a ejecutar.

        Precondición: el CPU core está libre (process=None).
        El scheduler debe:
            1. Elegir el proceso según su algoritmo
            2. Retirarlo de ready_queue
            3. NO cambiar el estado (lo hace el dispatcher)

        Args:
            current_tick: Tick actual de la simulación

        Returns:
            El PCB seleccionado, o None si la cola está vacía.
        """
        pass

    def should_preempt(self, current: PCB, current_tick: int) -> bool:
        """
        ¿Debe el proceso actual ser desalojado?

        Llamado CADA TICK para schedulers apropiativos.
        Por defecto retorna False (no apropiativo).

        Args:
            current     : PCB del proceso actualmente en CPU
            current_tick: Tick actual

        Returns:
            True si se debe expulsar al proceso actual.
        """
        return False

    def on_tick(self, current_tick: int) -> None:
        """
        Hook llamado en cada tick, antes de la lógica principal.
        Usado para actualizar estadísticas de aging, MLFQ, etc.
        """
        pass

    def queue_length(self) -> int:
        """Número de procesos en la cola READY."""
        return len(self.ready_queue)

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del algoritmo para mostrar en la UI."""
        pass

    @property
    def is_preemptive(self) -> bool:
        """True si el scheduler puede expulsar procesos."""
        return False
