"""
kernel/models/interrupt.py — Modelo de Interrupciones.

Las interrupciones son eventos que requieren atención inmediata del SO.
En PatatOS v2, las interrupciones NO son puramente aleatorias (req1.txt):
    - I/O requests emergen de la probabilidad io_probability del proceso
    - TIMER emerge de la expiración del quantum
    - PROCESS_ERROR emerge de has_error + estado del proceso
    - SYSCALL emerge de syscall_probability del proceso

La aleatoriedad es DETERMINÍSTICA por PID+tick (usando hash SHA256),
lo que hace la simulación reproducible y predecible para análisis académico.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class InterruptType(str, Enum):
    """
    Tipos de interrupciones del sistema.

    Hardware:
        TIMER        : Quantum expirado / interrupción de reloj
        IO_REQUEST   : Proceso solicita un dispositivo I/O
        IO_COMPLETE  : Dispositivo terminó de atender al proceso

    Software:
        SYSCALL      : Llamada al sistema (interrupción de software)
        PROCESS_ERROR: Error fatal en el proceso (segfault, división por 0...)
        PAGE_FAULT   : Fallo de página (RESERVADO — integración futura de VM)
    """
    # Hardware
    TIMER         = "TIMER"
    IO_REQUEST    = "IO_REQUEST"
    IO_COMPLETE   = "IO_COMPLETE"

    # Software
    SYSCALL       = "SYSCALL"
    PROCESS_ERROR = "PROCESS_ERROR"
    PAGE_FAULT    = "PAGE_FAULT"   # Reservado para paginación virtual


@dataclass
class Interrupt:
    """
    Representa una interrupción pendiente de procesar.

    El InterruptController mantiene una cola de estas interrupciones.
    El engine las procesa al inicio de cada tick (máxima prioridad).
    """
    type: InterruptType
    pid: Optional[int] = None       # Proceso involucrado (None = global)
    device: Optional[str] = None    # Dispositivo I/O (para IO_REQUEST/COMPLETE)
    duration: int = 0               # Ticks de servicio estimados
    tick: int = 0                   # Tick en que se generó
    payload: Dict[str, Any] = field(default_factory=dict)
    """Datos adicionales dependientes del tipo de interrupción."""

    @property
    def priority(self) -> int:
        """
        Prioridad de la interrupción para el controlador.
        Menor valor = mayor prioridad (procesada primero).

        Hardware:
            TIMER:         0 (máxima prioridad)
            IO_COMPLETE:   1
            IO_REQUEST:    2
        Software:
            PROCESS_ERROR: 3
            SYSCALL:       4
            PAGE_FAULT:    5
        """
        _prio = {
            InterruptType.TIMER:         0,
            InterruptType.IO_COMPLETE:   1,
            InterruptType.IO_REQUEST:    2,
            InterruptType.PROCESS_ERROR: 3,
            InterruptType.SYSCALL:       4,
            InterruptType.PAGE_FAULT:    5,
        }
        return _prio.get(self.type, 9)


# ── Helpers para probabilidad determinística ───────────────────────────────────

def deterministic_probability(pid: int, tick: int, salt: str) -> float:
    """
    Genera una probabilidad determinística basada en PID + tick + salt.

    Por qué determinístico y no random():
        - Reproducible: misma semilla → misma secuencia de eventos
        - No acumulativo: no depende del estado interno del RNG
        - Por proceso: cada proceso tiene su propia "personalidad" de I/O

    Basado en SHA-256 (del proyecto SO_final).

    Args:
        pid : PID del proceso
        tick: Tick actual
        salt: Tipo de evento ("io", "syscall", "error")

    Returns:
        Float en [0.0, 1.0)
    """
    key = f"{pid}-{tick}-{salt}"
    h = hashlib.sha256(key.encode()).hexdigest()
    x = int(h[:8], 16)
    return x / 0xFFFFFFFF


def deterministic_duration(pid: int, salt: str, minimum: int, maximum: int) -> int:
    """
    Genera una duración determinística (en ticks) para un evento.

    Args:
        pid    : PID del proceso
        salt   : Tipo de evento ("io_disk", "syscall", etc.)
        minimum: Mínimo de ticks
        maximum: Máximo de ticks

    Returns:
        Entero en [minimum, maximum]
    """
    minimum = max(1, minimum)
    maximum = max(minimum, maximum)
    key = f"{pid}-{salt}"
    h = hashlib.sha256(key.encode()).hexdigest()
    x = int(h[:8], 16)
    return minimum + (x % (maximum - minimum + 1))
