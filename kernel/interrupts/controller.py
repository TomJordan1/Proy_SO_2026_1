"""
kernel/interrupts/controller.py — Controlador de Interrupciones.

Las interrupciones NO son puramente aleatorias (req1.txt):
    - TIMER      : Emitida por el scheduler al expirar el quantum
    - IO_REQUEST : Emitida por el proceso según io_probability (determinístico)
    - IO_COMPLETE: Emitida por el dispositivo al completar servicio
    - SYSCALL    : Emitida por el proceso según syscall_probability
    - PROCESS_ERROR: Emitida si has_error + probabilidad configurable

El controlador mantiene una cola ordenada por prioridad.
El engine vacía esta cola al inicio de cada tick.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from ..models.interrupt import Interrupt, InterruptType


class InterruptController:
    """
    Controlador de interrupciones del sistema.

    Mantiene una cola de interrupciones pendientes, ordenada por prioridad.
    El engine llama a `drain()` al inicio de cada tick para procesarlas.
    """

    def __init__(self) -> None:
        self._pending: List[Interrupt] = []
        self.total_raised: int = 0
        self.count_by_type: dict = {t.value: 0 for t in InterruptType}
        self._handlers: dict = {}

    def raise_interrupt(self, interrupt: Interrupt) -> None:
        """
        Agrega una interrupción a la cola pendiente.
        La cola se mantiene ordenada por prioridad.
        """
        self._pending.append(interrupt)
        self._pending.sort(key=lambda i: i.priority)
        self.total_raised += 1
        self.count_by_type[interrupt.type.value] = (
            self.count_by_type.get(interrupt.type.value, 0) + 1
        )

    def drain(self) -> List[Interrupt]:
        """
        Retorna y vacía todas las interrupciones pendientes.
        Llamado al inicio de cada tick por el engine.
        """
        pending = list(self._pending)
        self._pending.clear()
        return pending

    def has_pending(self) -> bool:
        return len(self._pending) > 0

    def register_handler(
        self,
        int_type: InterruptType,
        handler: Callable[[Interrupt], None],
    ) -> None:
        """Registra un manejador para un tipo de interrupción (extensión futura)."""
        self._handlers[int_type] = handler

    def get_stats(self) -> dict:
        """Estadísticas para la UI / métricas."""
        return {
            "total_raised":   self.total_raised,
            "by_type":        dict(self.count_by_type),
            "pending_count":  len(self._pending),
        }

    def reset(self) -> None:
        self._pending.clear()
        self.total_raised = 0
        self.count_by_type = {t.value: 0 for t in InterruptType}
