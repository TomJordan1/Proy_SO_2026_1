"""
kernel/scheduler/srtf.py — Shortest Remaining Time First (expropiativo).

Versión apropiativa de SJF.
En cada tick, compara el remaining_time del proceso en CPU con todos los
procesos en READY. Si alguno tiene menor tiempo restante, preempt.

Efecto: minimiza el tiempo promedio de espera (óptimo teórico).
Costo: muchos context switches si hay procesos con tiempos similares.
"""
from __future__ import annotations
from typing import Optional
from .base import BaseScheduler
from ..models.pcb import PCB, ProcessState


class SRTFScheduler(BaseScheduler):
    """
    SRTF — Shortest Remaining Time First (expropiativo).
    Verifica en cada tick si un proceso más corto llegó a READY.
    """

    def select_next(self, current_tick: int) -> Optional[PCB]:
        if not self.ready_queue:
            return None
        # El proceso con menor tiempo RESTANTE
        shortest = min(self.ready_queue, key=lambda p: (p.remaining_time, p.arrival_tick))
        self.ready_queue.remove(shortest)
        return shortest

    def should_preempt(self, current: PCB, current_tick: int) -> bool:
        """
        Preempt si hay un proceso en READY con menor remaining_time.
        Se llama cada tick por el engine.
        """
        if not self.ready_queue:
            return False
        best_in_queue = min(self.ready_queue, key=lambda p: p.remaining_time)
        return best_in_queue.remaining_time < current.remaining_time

    @property
    def name(self) -> str:
        return "SRTF"

    @property
    def is_preemptive(self) -> bool:
        return True
