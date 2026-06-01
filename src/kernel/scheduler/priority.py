"""
kernel/scheduler/priority.py — Priority Scheduling con Aging.

Elige el proceso con MENOR valor de priority (0 = más urgente).

Modos:
    Preemptivo (preemptive=True):
        Si llega un proceso con mayor prioridad, el actual es desalojado.

    No apropiativo (preemptive=False):
        El proceso actual ejecuta hasta terminar o I/O.

Aging (anti-starvation):
    Cada `aging_interval` ticks en READY, la prioridad del proceso
    se DECREMENTA en 1 (aumenta su urgencia).
    Evita que procesos de baja prioridad esperen indefinidamente.
    El aging se resetea cuando el proceso obtiene CPU.
"""
from __future__ import annotations
from typing import Optional
from .base import BaseScheduler
from ..models.pcb import PCB, ProcessState


class PriorityScheduler(BaseScheduler):
    """
    Priority Scheduling (apropiativo o no) con Aging configurable.
    Prioridad: 0 = máxima urgencia, 9 = mínima urgencia.
    """

    def __init__(
        self,
        preemptive: bool = True,
        aging_enabled: bool = True,
        aging_interval: int = 20,
    ) -> None:
        super().__init__()
        self.preemptive = preemptive
        self.aging_enabled = aging_enabled
        self.aging_interval = aging_interval

    def select_next(self, current_tick: int) -> Optional[PCB]:
        if not self.ready_queue:
            return None
        # Proceso con mayor prioridad (menor valor numérico)
        best = min(self.ready_queue, key=lambda p: (p.priority, p.arrival_tick))
        self.ready_queue.remove(best)
        return best

    def should_preempt(self, current: PCB, current_tick: int) -> bool:
        """Preempt solo si hay un proceso de MAYOR prioridad en cola."""
        if not self.preemptive or not self.ready_queue:
            return False
        best_in_queue = min(self.ready_queue, key=lambda p: p.priority)
        return best_in_queue.priority < current.priority

    def on_tick(self, current_tick: int) -> None:
        """Aplica aging a los procesos en READY que llevan mucho tiempo esperando."""
        if not self.aging_enabled:
            return
        for pcb in self.ready_queue:
            if pcb.waiting_time > 0 and pcb.waiting_time % self.aging_interval == 0:
                if pcb.priority > 0:
                    pcb.priority -= 1      # Sube en prioridad (menor valor)
                    pcb.starvation_count += 1

    @property
    def name(self) -> str:
        mode = "Preemptivo" if self.preemptive else "No Preemptivo"
        return f"Priority ({mode})"

    @property
    def is_preemptive(self) -> bool:
        return self.preemptive
