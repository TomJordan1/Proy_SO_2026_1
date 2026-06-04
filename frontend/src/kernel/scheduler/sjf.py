"""
kernel/scheduler/sjf.py — Shortest Job First (No expropiativo).

Elige el proceso con menor burst_time (tiempo de CPU estimado).
No expropiativo: el proceso en CPU ejecuta hasta terminar o ir a WAITING.
Puede causar starvation de procesos largos (aging mitiga esto).
"""
from __future__ import annotations
from typing import Optional
from .base import BaseScheduler
from ..models.pcb import PCB


class SJFScheduler(BaseScheduler):
    """
    SJF — Shortest Job First (no expropiativo).
    Minimiza el tiempo promedio de espera si los burst_times son conocidos.
    En la realidad, el burst_time es estimado; aquí es exacto (simulación).
    """

    def select_next(self, current_tick: int) -> Optional[PCB]:
        if not self.ready_queue:
            return None
        # El proceso más corto (menor burst_time)
        shortest = min(self.ready_queue, key=lambda p: (p.burst_time, p.arrival_tick))
        self.ready_queue.remove(shortest)
        return shortest

    @property
    def name(self) -> str:
        return "SJF"

    @property
    def is_preemptive(self) -> bool:
        return False
