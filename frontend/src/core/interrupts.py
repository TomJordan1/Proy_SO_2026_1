"""
core/interrupts.py — Sistema de Interrupciones.

Las interrupciones son eventos ASÍNCRONOS que interrumpen el flujo normal
de ejecución y requieren atención inmediata del SO.

En un SO real, las interrupciones son señales de hardware o software
que suspenden la ejecución actual y transfieren el control al SO.

Tipos de interrupciones en PatatOS:
  ┌────────────────┬──────────────────────────────────────────────────────┐
  │ Tipo           │ Descripción                                          │
  ├────────────────┼──────────────────────────────────────────────────────┤
  │ TIMER          │ Interrupción de reloj (quantum expired en RR)        │
  │ IO_REQUEST     │ Proceso necesita un dispositivo I/O                  │
  │ IO_COMPLETE    │ Dispositivo I/O terminó de atender un proceso        │
  │ PROCESS_ERROR  │ Error fatal: proceso termina con exit_code=-1        │
  └────────────────┴──────────────────────────────────────────────────────┘

Generación aleatoria (según requerimientos del proyecto):
  - Interrupciones entre 5 y 20 ticks de intervalo (aleatorio)
  - Duración de I/O: 5 a 20 ticks (aleatorio)
  - Errores: 0.5% de probabilidad por proceso por tick
  - I/O requests: 10% de probabilidad por proceso por tick

El sistema de interrupciones es la base para eventos futuros como
interrupciones de hardware adicionales o excepciones de sistema.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import PCB

from utils.randomizer import random_io_duration, random_interrupt_interval, random_device


# ─────────────────────────────────────────────────────────────────────────────
# Tipos de interrupciones
# ─────────────────────────────────────────────────────────────────────────────

class InterruptType(str, Enum):
    """
    Tipos de interrupciones del sistema.

    str + Enum: permite comparar con strings y mostrar en logs.
    """
    TIMER         = "TIMER"         # Quantum de Round Robin expiró
    IO_REQUEST    = "IO_REQUEST"    # Proceso solicita un dispositivo I/O
    IO_COMPLETE   = "IO_COMPLETE"   # Dispositivo terminó de atender
    PROCESS_ERROR = "PROCESS_ERROR" # Error fatal en el proceso


# ─────────────────────────────────────────────────────────────────────────────
# Estructura de una Interrupción
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Interrupt:
    """
    Representa una interrupción pendiente de procesar.

    Attributes:
        type    : Tipo de interrupción (ver InterruptType)
        pid     : PID del proceso involucrado (None = interrupción global)
        device  : Dispositivo I/O involucrado (para IO_REQUEST/COMPLETE)
        duration: Ticks de espera (para IO_REQUEST)
        tick    : Tick en que se generó
    """
    type: InterruptType
    pid: Optional[int] = None
    device: Optional[str] = None
    duration: int = 0
    tick: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Cola de Interrupciones
# ─────────────────────────────────────────────────────────────────────────────

class InterruptQueue:
    """
    Cola de interrupciones pendientes de procesar.

    El engine procesa las interrupciones al inicio de cada tick,
    ANTES de ejecutar procesos. Esto refleja la realidad:
    las interrupciones tienen máxima prioridad en el SO.

    Implementación: lista FIFO simple
    (en un SO real sería una cola de prioridades por tipo de interrupción)
    """

    def __init__(self):
        self._queue: List[Interrupt] = []

    def push(self, interrupt: Interrupt) -> None:
        """Agrega una interrupción a la cola."""
        self._queue.append(interrupt)

    def pop(self) -> Optional[Interrupt]:
        """
        Extrae la siguiente interrupción (FIFO).
        Retorna None si la cola está vacía.
        """
        return self._queue.pop(0) if self._queue else None

    def has_pending(self) -> bool:
        """True si hay interrupciones esperando ser procesadas."""
        return bool(self._queue)

    def clear(self) -> None:
        """Elimina todas las interrupciones pendientes."""
        self._queue.clear()

    def __len__(self) -> int:
        return len(self._queue)


# ─────────────────────────────────────────────────────────────────────────────
# Generador de Interrupciones Aleatorias
# ─────────────────────────────────────────────────────────────────────────────

class RandomInterruptGenerator:
    """
    Genera interrupciones aleatorias para simular el comportamiento
    no predecible de los procesos y el hardware.

    Según los requerimientos del proyecto:
      - Intervalo: 5-20 ticks entre interrupciones de timer globales
      - I/O requests: 10% de probabilidad por proceso por tick
      - Errores fatales: 0.5% de probabilidad por proceso por tick

    Llamar a check() en cada tick del engine.

    NOTA sobre probabilidades:
      Si hay 5 procesos en RUNNING con P(IO) = 10%,
      en promedio ocurrirán 0.5 eventos I/O por tick.
      Esto crea un flujo realista de interrupciones.
    """

    # Probabilidades según requerimientos
    IO_PROBABILITY    = 0.10   # 10% por proceso por tick
    ERROR_PROBABILITY = 0.005  # 0.5% por proceso por tick (requerimiento)

    def __init__(self):
        # Tick en que ocurrirá la próxima interrupción global de timer
        self._next_timer_tick: int = random_interrupt_interval()

    def check(
        self,
        current_tick: int,
        running_process: Optional[PCB]
    ) -> List[Interrupt]:
        """
        Genera interrupciones que deben ocurrir en este tick.

        Args:
            current_tick   : Tick actual de la simulación
            running_process: Proceso actualmente en la CPU (o None)

        Returns:
            Lista de interrupciones generadas (puede estar vacía)
        """
        interrupts: List[Interrupt] = []

        if running_process is not None:
            # ── I/O Request aleatorio ─────────────────────────────────────────
            # El proceso en ejecución puede necesitar un dispositivo I/O
            if random.random() < self.IO_PROBABILITY:
                device = random_device()
                duration = random_io_duration()
                interrupts.append(Interrupt(
                    type=InterruptType.IO_REQUEST,
                    pid=running_process.pid,
                    device=device,
                    duration=duration,
                    tick=current_tick
                ))

            # ── Error Fatal aleatorio ─────────────────────────────────────────
            # Probabilidad muy baja (0.5%) de que el proceso falle
            elif random.random() < self.ERROR_PROBABILITY:
                interrupts.append(Interrupt(
                    type=InterruptType.PROCESS_ERROR,
                    pid=running_process.pid,
                    tick=current_tick
                ))

        # ── Interrupción de Timer Global ──────────────────────────────────────
        # Ocurre cada 5-20 ticks independientemente del proceso actual
        if current_tick >= self._next_timer_tick:
            interrupts.append(Interrupt(
                type=InterruptType.TIMER,
                tick=current_tick
            ))
            # Programar la próxima interrupción de timer
            self._next_timer_tick = current_tick + random_interrupt_interval()

        return interrupts

    def reset(self) -> None:
        """Reinicia el generador."""
        self._next_timer_tick = random_interrupt_interval()
