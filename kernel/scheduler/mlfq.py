"""
kernel/scheduler/mlfq.py — Multilevel Feedback Queue (STUB).

Estado: PREPARADO PARA INTEGRACIÓN FUTURA.

Este módulo define la interfaz completa del MLFQ y expone la clase
MLFQScheduler. El engine ya puede instanciarlo (aparecerá en el combo
de la UI), pero la lógica interna está marcada como TODO.

Cuando se integre completamente:
    1. Descomentar la lógica de _queues y _quantums
    2. Implementar _apply_demotion() y _apply_promotion()
    3. Conectar pcb.mlfq_level en el engine
    4. Agregar la vista de múltiples colas en la UI

Diseño planificado (para referencia):
    Cola 0 (Q=4):  Alta prioridad. Nuevo proceso entra aquí.
    Cola 1 (Q=8):  Media prioridad. Degradado si agota Q en cola 0.
    Cola 2 (Q=∞):  FCFS. Procesos largo-plazo (CPU-bound puro).

    Reglas:
        - Al llegar: entra a Cola 0
        - Agota quantum: baja un nivel (demotion)
        - Espera demasiado: sube un nivel (promotion / boost)
        - I/O voluntaria antes de agotar quantum: permanece en mismo nivel
"""
from __future__ import annotations

import warnings
from typing import Optional, List
from .base import BaseScheduler
from ..models.pcb import PCB


# Quantums por nivel (configurable en la futura versión completa)
_DEFAULT_QUANTUMS = [4, 8, 0]  # 0 = FCFS (infinito)
_NUM_LEVELS = 3


class MLFQScheduler(BaseScheduler):
    """
    MLFQ — Multilevel Feedback Queue.

    ESTADO: STUB — lógica básica de fallback a FCFS mientras se integra.
    Los procesos entran a la cola 0 y se procesan en orden FCFS
    entre niveles (FCFS dentro de cada nivel también, por ahora).

    El campo pcb.mlfq_level se usa para futuras vistas de la UI.
    """

    def __init__(self, quantums: Optional[List[int]] = None) -> None:
        super().__init__()
        self.quantums: List[int] = quantums or list(_DEFAULT_QUANTUMS)
        # Colas separadas por nivel (preparadas para la integración)
        self._queues: List[List[PCB]] = [[] for _ in range(_NUM_LEVELS)]
        warnings.warn(
            "MLFQScheduler está en modo STUB. "
            "La lógica de degradación/promoción no está implementada aún.",
            UserWarning,
            stacklevel=2,
        )

    def add_process(self, pcb: PCB) -> None:
        """Nuevo proceso entra al nivel 0 (mayor prioridad)."""
        pcb.state = __import__("kernel.models.pcb", fromlist=["ProcessState"]).ProcessState.READY
        pcb.mlfq_level = 0
        self._queues[0].append(pcb)
        # También en ready_queue para compatibilidad con la UI actual
        self.ready_queue.append(pcb)

    def select_next(self, current_tick: int) -> Optional[PCB]:
        """
        Elige el proceso de mayor nivel disponible.
        (Implementación básica: FCFS entre niveles).
        """
        for level in range(_NUM_LEVELS):
            if self._queues[level]:
                pcb = self._queues[level].pop(0)
                # Sincronizar con ready_queue
                if pcb in self.ready_queue:
                    self.ready_queue.remove(pcb)
                quantum = self.quantums[level]
                pcb.quantum_used = 0
                pcb.quantum_remaining = quantum if quantum > 0 else 9999
                return pcb
        return None

    def should_preempt(self, current: PCB, current_tick: int) -> bool:
        """
        Preempt al agotar el quantum del nivel actual.
        TODO: implementar demotion al nivel siguiente.
        """
        level = min(current.mlfq_level, _NUM_LEVELS - 1)
        quantum = self.quantums[level]
        if quantum <= 0:
            return False  # Nivel FCFS: no preempt por quantum
        return current.quantum_used >= quantum

    def on_tick(self, current_tick: int) -> None:
        """
        TODO: Implementar boost periódico (promotion de procesos viejos).
        Cada N ticks, mover todos los procesos al nivel 0.
        Evita starvation en cola 2.
        """
        pass  # Pendiente de implementación completa

    @property
    def name(self) -> str:
        return "MLFQ (Beta)"

    @property
    def is_preemptive(self) -> bool:
        return True
