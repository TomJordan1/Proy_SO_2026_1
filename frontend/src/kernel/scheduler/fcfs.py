"""
kernel/scheduler/fcfs.py — First Come, First Served.

No expropiativo. Orden estricto de llegada.
El proceso que llega primero, ejecuta hasta completar su burst (o I/O).
"""
from __future__ import annotations
from typing import Optional
from .base import BaseScheduler
from ..models.pcb import PCB


class FCFSScheduler(BaseScheduler):
    """
    FCFS — First Come, First Served.
    No expropiativo. Sin starvation de procesos cortos... ¡pero convoy effect!
    """

    def add_process(self, pcb: PCB) -> None:
        super().add_process(pcb)
        # Ordenar por arrival_tick para garantizar orden real de llegada
        self.ready_queue.sort(key=lambda p: p.arrival_tick)

    def select_next(self, current_tick: int) -> Optional[PCB]:
        if self.ready_queue:
            return self.ready_queue.pop(0)
        return None

    @property
    def name(self) -> str:
        return "FCFS"

    @property
    def is_preemptive(self) -> bool:
        return False
