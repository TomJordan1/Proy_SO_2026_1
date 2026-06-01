"""
kernel/dispatcher/dispatcher.py — Despachador de Procesos.

El Dispatcher es responsable de:
    1. Salvar el contexto del proceso saliente (registros, PC, estado)
    2. Pagar el costo de context switch (ticks de overhead)
    3. Cargar el contexto del proceso entrante
    4. Notificar al engine del cambio

Costo de context switch (req1.txt):
    context_switch_cost > 0 → la CPU pasa esos ticks en overhead.
    Durante el switch: CPU reporta "SWITCHING" en la UI.
    Esta métrica impacta REALMENTE el throughput del sistema.

Multi-CPU: cada CPUCore tiene su propio switch tracking.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ..models.pcb import PCB, ProcessState


@dataclass
class ContextSwitchEvent:
    """Registro de un cambio de contexto para métricas y log."""
    tick: int
    outgoing_pid: Optional[int]    # None si la CPU estaba idle
    incoming_pid: Optional[int]    # None si la CPU queda idle
    cpu_id: int
    cost_ticks: int


class Dispatcher:
    """
    Despachador del sistema operativo simulado.

    Instancia global por engine. Recibe CPUCore + próximo proceso
    y orquesta el cambio de contexto.

    context_switch_cost:
        0  → cambio instantáneo (sin overhead)
        1+ → la CPU pasa N ticks en estado "SWITCHING" antes de ejecutar
    """

    def __init__(self, context_switch_cost: int = 1) -> None:
        self.context_switch_cost: int = context_switch_cost
        self.total_switches: int = 0
        self.total_switch_overhead_ticks: int = 0
        self.history: List[ContextSwitchEvent] = []
        """Historial de switches (últimos 100) para métricas."""

        self._log_callback: Optional[Callable[[str], None]] = None

    def set_log_callback(self, callback: Callable[[str], None]) -> None:
        """Permite al engine suscribir su función de log."""
        self._log_callback = callback

    def _log(self, msg: str) -> None:
        if self._log_callback:
            self._log_callback(msg)

    def dispatch(
        self,
        outgoing: Optional[PCB],
        incoming: Optional[PCB],
        cpu_id: int,
        current_tick: int,
    ) -> int:
        """
        Realiza un cambio de contexto.

        Guarda el contexto del proceso saliente y lo pone en READY.
        Marca el proceso entrante como RUNNING.

        Args:
            outgoing    : Proceso que sale de la CPU (puede ser None si idle)
            incoming    : Proceso que entra a la CPU (puede ser None si queda idle)
            cpu_id      : ID del core involucrado
            current_tick: Tick actual

        Returns:
            Costo real del switch en ticks (para que el core quede en overhead).
        """
        # 1. Salvar contexto del proceso saliente
        if outgoing and outgoing.state == ProcessState.RUNNING:
            # El proceso vuelve a READY (será reinsertado en la cola por el engine)
            outgoing.state = ProcessState.READY
            outgoing.cpu_id = None
            self._log(
                f"[T={current_tick}] CPU{cpu_id}: CTX-OUT P{outgoing.pid} "
                f"({outgoing.name}) — PC=0x{outgoing.program_counter:04X}"
            )

        # 2. Cargar contexto del proceso entrante
        if incoming:
            incoming.state = ProcessState.RUNNING
            incoming.cpu_id = cpu_id
            incoming.quantum_used = 0
            if incoming.start_tick is None:
                incoming.start_tick = current_tick
            self._log(
                f"[T={current_tick}] CPU{cpu_id}: CTX-IN  P{incoming.pid} "
                f"({incoming.name}) — prio={incoming.priority} "
                f"rem={incoming.remaining_time}t"
            )

        # 3. Registrar el switch
        cost = self.context_switch_cost
        event = ContextSwitchEvent(
            tick=current_tick,
            outgoing_pid=outgoing.pid if outgoing else None,
            incoming_pid=incoming.pid if incoming else None,
            cpu_id=cpu_id,
            cost_ticks=cost,
        )
        self.history.append(event)
        if len(self.history) > 100:
            self.history.pop(0)

        self.total_switches += 1
        self.total_switch_overhead_ticks += cost

        return cost

    def reset(self) -> None:
        """Reinicia contadores para reset de simulación."""
        self.total_switches = 0
        self.total_switch_overhead_ticks = 0
        self.history.clear()
