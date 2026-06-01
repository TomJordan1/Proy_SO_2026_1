"""
core/models.py — Definición del PCB (Process Control Block) y estados de proceso.

El PCB es la estructura fundamental que el SO usa para administrar cada proceso.
Contiene TODA la información necesaria para gestionar la ejecución, pausa
y reanudación de un proceso. En un SO real, el PCB vive en el kernel space.

Diagrama de transiciones de estados:

    ┌─────┐     admisión      ┌───────┐   dispatch   ┌─────────┐
    │ NEW │ ────────────────► │ READY │ ───────────► │ RUNNING │
    └─────┘                  └───────┘               └────┬────┘
                                  ▲                       │
                                  │  I/O completa    I/O request /
                              ┌───┴─────┐            error / quantum
                              │ WAITING │ ◄───────────────┘
                              └─────────┘
                                                    ┌────────────┐
                                              ──────► TERMINATED │
                                                    └────────────┘

Uso de dataclasses:
    - Evita boilerplate (__init__, __repr__)
    - Campos con valores por defecto
    - Inmutabilidad opcional con frozen=True (no usamos aquí por flexibilidad)
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Generador global de PIDs (se reinicia en reset de simulación)
# itertools.count() genera 1, 2, 3, 4, ... de forma eficiente
# ─────────────────────────────────────────────────────────────────────────────
_pid_counter = itertools.count(1)


def reset_pid_counter() -> None:
    """Reinicia el contador de PIDs. Llamar solo al hacer Reset de simulación."""
    global _pid_counter
    _pid_counter = itertools.count(1)


def next_pid() -> int:
    """Retorna el siguiente PID disponible."""
    return next(_pid_counter)


# ─────────────────────────────────────────────────────────────────────────────
# Estados de proceso
# ─────────────────────────────────────────────────────────────────────────────

class ProcessState(str, Enum):
    """
    Estados posibles de un proceso en el simulador.

    str + Enum permite comparar con strings: state == "RUNNING"
    También permite serializar fácilmente a JSON/log.

    Transiciones válidas:
        NEW        → READY      (admisión, memoria asignada)
        READY      → RUNNING    (dispatcher lo selecciona)
        RUNNING    → READY      (quantum expira en RR, preemption)
        RUNNING    → WAITING    (solicita I/O o interrupción)
        RUNNING    → TERMINATED (burst_time agotado o error fatal)
        WAITING    → READY      (I/O completado)
    """
    NEW        = "NEW"
    READY      = "READY"
    RUNNING    = "RUNNING"
    WAITING    = "WAITING"
    TERMINATED = "TERMINATED"


# ─────────────────────────────────────────────────────────────────────────────
# PCB — Process Control Block
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PCB:
    """
    Process Control Block — Bloque de Control de Proceso.

    Esta estructura almacena TODA la información de un proceso.
    El dispatcher la usa para guardar y restaurar el contexto
    durante un cambio de proceso (context switch).

    ┌─────────────────────────────────────────────────────┐
    │              PCB Structure                          │
    ├─────────────────────────────────────────────────────┤
    │ Identidad: pid, name, is_system                     │
    │ Estado:    state, program_counter                   │
    │ CPU:       burst_time, remaining_time, quantum_used │
    │ Memoria:   memory_address, memory_size              │
    │ I/O:       io_device, io_remaining                  │
    │ Scheduling: priority, arrival_tick, start_tick      │
    │ Métricas:  waiting_time, finish_tick                │
    └─────────────────────────────────────────────────────┘

    Los campos sin default van ANTES de los que tienen default.
    """

    # ── Identidad ────────────────────────────────────────────────────────────
    name: str                           # Nombre descriptivo ("chrome.exe", "P1")

    # ── Scheduling ───────────────────────────────────────────────────────────
    burst_time: int = 20                # Ticks totales de CPU que necesita el proceso
    priority: int = 5                   # Prioridad: 0=más alta, 9=más baja
    memory_size: int = 1                # Bloques de memoria requeridos

    # ── Generado automáticamente ─────────────────────────────────────────────
    pid: int = field(default_factory=next_pid)  # Identificador único

    # ── Estado ───────────────────────────────────────────────────────────────
    state: ProcessState = ProcessState.NEW
    is_system: bool = False             # True si proviene del SO real (psutil)

    # Contador de programa simulado: avanza con cada instrucción ejecutada
    # En un SO real: apunta a la siguiente instrucción en memoria
    program_counter: int = 0

    # Tiempo restante de CPU (se decrementa cada tick que el proceso está RUNNING)
    remaining_time: int = 0             # Se inicializa en __post_init__

    # Ticks usados en el quantum actual (para Round Robin)
    quantum_used: int = 0

    # ── Memoria ──────────────────────────────────────────────────────────────
    # Índice del primer bloque de memoria asignado (-1 = sin asignar)
    # Esto es la "dirección física" en nuestra simulación de memoria plana
    # EXTENSIBILIDAD: para memoria virtual, este campo mapearía a un frame físico
    memory_address: int = -1

    # ── I/O ──────────────────────────────────────────────────────────────────
    io_device: Optional[str] = None     # Dispositivo actual ("KEYBOARD", "DISK", etc.)
    io_remaining: int = 0               # Ticks restantes de espera I/O

    # ── Timestamps para métricas ─────────────────────────────────────────────
    arrival_tick: int = 0               # Tick de llegada al sistema
    start_tick: Optional[int] = None    # Tick de primera ejecución en CPU
    finish_tick: Optional[int] = None   # Tick de finalización

    # Acumulado de ticks en estado READY (esperando en cola sin ejecutar)
    waiting_time: int = 0

    # ── Error ─────────────────────────────────────────────────────────────────
    has_error: bool = False             # Si el proceso fallará aleatoriamente
    exit_code: int = 0                  # 0 = éxito, -1 = error

    def __post_init__(self):
        """Inicialización posterior al __init__ generado por dataclass."""
        # remaining_time debe empezar igual a burst_time
        if self.remaining_time == 0:
            self.remaining_time = self.burst_time

    # ── Propiedades calculadas ────────────────────────────────────────────────

    @property
    def response_time(self) -> int:
        """
        Tiempo de respuesta: desde la llegada hasta la PRIMERA ejecución.
        Fórmula: start_tick - arrival_tick
        Mide qué tan rápido el sistema comienza a atender el proceso.
        """
        if self.start_tick is None:
            return 0
        return self.start_tick - self.arrival_tick

    @property
    def turnaround_time(self) -> int:
        """
        Tiempo de retorno: desde llegada hasta finalización completa.
        Fórmula: finish_tick - arrival_tick
        Incluye: tiempo en cola + tiempo de CPU + tiempo de I/O
        """
        if self.finish_tick is None:
            return 0
        return self.finish_tick - self.arrival_tick

    @property
    def completion_percent(self) -> float:
        """Porcentaje de completitud (0-100)."""
        if self.burst_time == 0:
            return 100.0
        done = self.burst_time - self.remaining_time
        return min(100.0, (done / self.burst_time) * 100.0)
