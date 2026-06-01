"""
core/dispatcher.py — Despachador (Dispatcher).

El Dispatcher realiza el CAMBIO DE CONTEXTO (context switch) entre procesos.
Cuando el scheduler decide quién ejecuta, el dispatcher es el que:
  1. Actualiza el estado del proceso SALIENTE (→ READY si fue preempted)
  2. Actualiza el estado del proceso ENTRANTE (→ RUNNING)
  3. Registra el start_tick si es la primera ejecución
  4. Reinicia quantum_used del proceso entrante

En un SO real:
  - El context switch guarda todos los registros de CPU en el PCB del proceso saliente
  - Luego carga los registros del proceso entrante
  - Esto toma microsegundos (overhead del SO)

En nuestra simulación:
  - "Guardar registros" = actualizar estado del PCB
  - El program_counter ya avanza en el engine durante RUNNING
  - Registramos cuántos context switches ocurren (métrica de overhead)

Overhead del context switch:
  - FCFS: pocos context switches (solo al terminar o bloquearse)
  - Round Robin: muchos context switches (cada quantum)
  - A mayor quantum en RR → menos switches → más eficiente pero menos justo
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import PCB

from .models import ProcessState


class Dispatcher:
    """
    Realiza cambios de contexto entre procesos.

    Estadísticas:
      context_switch_count: número total de cambios de contexto
      (compara esto entre FCFS y RR para ver el overhead)
    """

    def __init__(self):
        self.context_switch_count: int = 0
        self.current_process: Optional[PCB] = None

    def dispatch(
        self,
        outgoing: Optional[PCB],
        incoming: Optional[PCB],
        current_tick: int,
        preempted: bool = False
    ) -> None:
        """
        Realiza el cambio de contexto.

        Args:
            outgoing    : Proceso que SALE de la CPU (None si estaba idle)
            incoming    : Proceso que ENTRA a la CPU (None para idle)
            current_tick: Tick actual (para registrar start_tick)
            preempted   : True si el proceso saliente fue expulsado (RR)

        Flujo detallado:
            ┌─ Si hay proceso saliente ──────────────────────────────────┐
            │  - Si fue preempted (RR): estado → READY, quantum_used = 0 │
            │  - Si terminó: el engine ya lo puso en TERMINATED          │
            │  - Si I/O: el engine ya lo puso en WAITING                 │
            └────────────────────────────────────────────────────────────┘
            ┌─ Si hay proceso entrante ──────────────────────────────────┐
            │  - Estado → RUNNING                                        │
            │  - Si es la primera ejecución: registrar start_tick        │
            │  - Reiniciar quantum_used = 0                              │
            └────────────────────────────────────────────────────────────┘
        """
        # ── Proceso SALIENTE ──────────────────────────────────────────────────
        if outgoing and outgoing != incoming:
            if preempted and outgoing.state == ProcessState.RUNNING:
                # Fue expulsado por quantum: vuelve a READY
                outgoing.state = ProcessState.READY
                outgoing.quantum_used = 0

        # ── Proceso ENTRANTE ──────────────────────────────────────────────────
        if incoming:
            incoming.state = ProcessState.RUNNING
            incoming.quantum_used = 0

            # Registrar el tick de inicio SOLO la primera vez que ejecuta
            # (para calcular response_time = start_tick - arrival_tick)
            if incoming.start_tick is None:
                incoming.start_tick = current_tick

        self.current_process = incoming
        self.context_switch_count += 1

    def release_cpu(self) -> None:
        """
        Libera la CPU sin asignar nuevo proceso.
        Usado cuando la cola READY está vacía (CPU idle).
        """
        self.current_process = None

    def reset(self) -> None:
        """Reinicia el dispatcher para una nueva simulación."""
        self.context_switch_count = 0
        self.current_process = None
