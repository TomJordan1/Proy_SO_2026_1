"""
kernel/scheduler/round_robin.py — Round Robin con Quantum Configurable.

Apropiativo. Cada proceso recibe exactamente `quantum` ticks de CPU.
Al expirar el quantum, el proceso vuelve al final de la cola READY.

Métricas interesantes de observar:
    - quantum pequeño → más context switches, mejor tiempo de respuesta
    - quantum grande  → se acerca a FCFS, menos overhead
    - El engine registra cada expiración de quantum en el log.
"""
from __future__ import annotations
from typing import Optional
from .base import BaseScheduler
from ..models.pcb import PCB


class RoundRobinScheduler(BaseScheduler):
    """
    Round Robin — apropiativo con quantum de tiempo fijo.
    El quantum se puede cambiar en caliente desde la UI.
    """

    def __init__(self, quantum: int = 4) -> None:
        super().__init__()
        self.quantum: int = quantum

    def select_next(self, current_tick: int) -> Optional[PCB]:
        if self.ready_queue:
            pcb = self.ready_queue.pop(0)
            pcb.quantum_used = 0
            pcb.quantum_remaining = self.quantum
            return pcb
        return None

    def should_preempt(self, current: PCB, current_tick: int) -> bool:
        """Preempt cuando el proceso agotó su quantum."""
        return current.quantum_used >= self.quantum

    @property
    def name(self) -> str:
        return f"Round Robin (Q={self.quantum})"

    @property
    def is_preemptive(self) -> bool:
        return True
