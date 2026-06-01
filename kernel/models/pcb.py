"""
kernel/models/pcb.py — Process Control Block y estados del proceso.

PCB v2: extendido con tipos de proceso, segmentos de memoria,
registros de CPU, probabilidades de I/O por tipo, y soporte
para algoritmos avanzados (aging, MLFQ futuro).

Tipos de proceso (req1.txt):
    CPU_BOUND:   Bursts largos, poco I/O. Ej: compiladores, renders.
    IO_BOUND:    Bursts cortos, mucho WAITING. Ej: bases de datos, discos.
    INTERACTIVE: Respuesta rápida requerida. Ej: editores, shells.
    SYSTEM:      Procesos del kernel, prioridad alta.

Segmentos de memoria (req1.txt — abstractamente):
    TEXT  : Código ejecutable (40% del tamaño)
    DATA  : Variables globales/estáticas (30%)
    HEAP  : Memoria dinámica (20%)
    STACK : Pila de llamadas (10%)

Program Counter: NO es decorativo. Avanza con cada instrucción simulada.
Registros: AX, BX, CX, DX — modificados aleatoriamente durante RUNNING.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

# ── Generador de PIDs ─────────────────────────────────────────────────────────
_pid_counter = itertools.count(1)


def reset_pid_counter() -> None:
    """Reinicia el contador de PIDs. Solo llamar en reset de simulación."""
    global _pid_counter
    _pid_counter = itertools.count(1)


def next_pid() -> int:
    return next(_pid_counter)


# ── Enums ─────────────────────────────────────────────────────────────────────

class ProcessState(str, Enum):
    """
    Estados de proceso con transiciones válidas:

        NEW ──(admisión)──► READY ──(dispatch)──► RUNNING
                               ▲                      │
                               │    (I/O done)        │ (I/O req / quantum / error)
                           WAITING ◄──────────────────┘
                                                      │ (burst agotado)
                                               TERMINATED
    """
    NEW        = "NEW"
    READY      = "READY"
    RUNNING    = "RUNNING"
    WAITING    = "WAITING"
    TERMINATED = "TERMINATED"


class ProcessType(str, Enum):
    """
    Perfil de comportamiento del proceso.
    Determina las probabilidades de I/O, duración de bursts y prioridad base.
    """
    CPU_BOUND   = "CPU_BOUND"    # Bursts largos, poco I/O
    IO_BOUND    = "IO_BOUND"     # Bursts cortos, mucho WAITING
    INTERACTIVE = "INTERACTIVE"  # Respuesta rápida (shell, editor)
    SYSTEM      = "SYSTEM"       # Kernel/OS, alta prioridad


# Probabilidades y rangos por tipo de proceso
_TYPE_PROFILES = {
    ProcessType.CPU_BOUND: {
        "io_probability":      0.05,
        "syscall_probability": 0.03,
        "burst_min": 30, "burst_max": 80,
        "priority_min": 4, "priority_max": 8,
        "mem_min_mb": 16,  "mem_max_mb": 128,
    },
    ProcessType.IO_BOUND: {
        "io_probability":      0.40,
        "syscall_probability": 0.08,
        "burst_min": 5,  "burst_max": 20,
        "priority_min": 3, "priority_max": 6,
        "mem_min_mb": 8,   "mem_max_mb": 64,
    },
    ProcessType.INTERACTIVE: {
        "io_probability":      0.25,
        "syscall_probability": 0.15,
        "burst_min": 3,  "burst_max": 15,
        "priority_min": 1, "priority_max": 4,
        "mem_min_mb": 4,   "mem_max_mb": 32,
    },
    ProcessType.SYSTEM: {
        "io_probability":      0.10,
        "syscall_probability": 0.20,
        "burst_min": 10, "burst_max": 40,
        "priority_min": 0, "priority_max": 2,
        "mem_min_mb": 4,   "mem_max_mb": 24,
    },
}


# ── PCB ───────────────────────────────────────────────────────────────────────

@dataclass
class PCB:
    """
    Process Control Block — Bloque de Control de Proceso (versión completa).

    Contiene toda la información necesaria para administrar el ciclo de
    vida de un proceso: estado, CPU, memoria, I/O, scheduling y métricas.
    """

    # ── Identidad ─────────────────────────────────────────────────────────────
    name: str
    process_type: ProcessType = ProcessType.CPU_BOUND

    # ── Scheduling ────────────────────────────────────────────────────────────
    burst_time: int = 20
    """Ticks totales de CPU requeridos por el proceso."""

    priority: int = 5
    """Prioridad: 0 = más alta, 9 = más baja."""

    # ── Memoria ───────────────────────────────────────────────────────────────
    memory_size: int = 32
    """Tamaño total de memoria requerida (MB)."""

    # Segmentos de espacio de proceso (req1: TEXT/DATA/HEAP/STACK)
    text_size: int = 0    # Código ejecutable (≈ 40%)
    data_size: int = 0    # Variables globales (≈ 30%)
    heap_size: int = 0    # Memoria dinámica  (≈ 20%)
    stack_size: int = 0   # Pila de llamadas  (≈ 10%)

    # ── Generado automáticamente ──────────────────────────────────────────────
    pid: int = field(default_factory=next_pid)
    state: ProcessState = ProcessState.NEW
    is_system: bool = False

    # ── CPU / Ejecución ───────────────────────────────────────────────────────
    program_counter: int = 0
    """PC: avanza instrucción a instrucción durante RUNNING. NO decorativo."""

    registers: Dict[str, int] = field(
        default_factory=lambda: {"AX": 0, "BX": 0, "CX": 0, "DX": 0}
    )
    """Registros simulados: se modifican aleatoriamente durante ejecución."""

    remaining_time: int = 0
    """Ticks de CPU que quedan para completar el burst."""

    quantum_used: int = 0
    """Ticks usados en el quantum actual (Round Robin / Priority-RR)."""

    quantum_remaining: int = 0
    """Ticks restantes del quantum actual (calculado por el scheduler)."""

    cpu_id: Optional[int] = None
    """ID del core que ejecuta este proceso (-1 = sin CPU asignado)."""

    # ── Dirección de memoria ──────────────────────────────────────────────────
    memory_base_address: int = -1
    """
    Dirección física base (MB) asignada por el MemoryManager.
    Con la MMU activa: dirección LÓGICA → traducida a física por la MMU.
    Futuro (paginación): será la base del espacio de páginas virtuales.
    -1 = sin memoria asignada.
    """

    # ── I/O ───────────────────────────────────────────────────────────────────
    io_device: Optional[str] = None
    """Dispositivo actual en uso (solo cuando state == WAITING)."""

    io_remaining: int = 0
    """Ticks restantes de servicio I/O."""

    io_probability: float = 0.10
    """Probabilidad de solicitar I/O en cada tick (según process_type)."""

    syscall_probability: float = 0.05
    """Probabilidad de syscall (interrupción de software) por tick."""

    # ── Timestamps ────────────────────────────────────────────────────────────
    arrival_tick: int = 0
    start_tick: Optional[int] = None     # Primer tick en CPU
    finish_tick: Optional[int] = None    # Tick de terminación

    # ── Métricas acumuladas ───────────────────────────────────────────────────
    waiting_time: int = 0
    """Ticks acumulados en estado READY sin ejecutar."""

    # ── Error ─────────────────────────────────────────────────────────────────
    has_error: bool = False
    """True si el proceso está destinado a fallar (determinístico por PID)."""

    exit_code: int = 0
    """0 = éxito, -1 = error fatal."""

    # ── Anti-starvation (Aging) ───────────────────────────────────────────────
    starvation_count: int = 0
    """Número de veces que el aging aumentó la prioridad de este proceso."""

    original_priority: int = -1
    """Prioridad original asignada (para métricas de aging)."""

    # ── MLFQ (preparado para integración futura) ──────────────────────────────
    mlfq_level: int = 0
    """
    Nivel actual en la cola MLFQ (0 = mayor prioridad).
    Actualmente no usado. Cuando se integre MLFQ:
      - El scheduler lee y escribe este campo
      - La UI muestra el nivel de degradación
    """

    def __post_init__(self):
        """Inicialización tras el __init__ generado por dataclass."""
        # remaining_time parte igual a burst_time
        if self.remaining_time == 0:
            self.remaining_time = self.burst_time

        # Guardar prioridad original para métricas de aging
        if self.original_priority == -1:
            self.original_priority = self.priority

        # Calcular segmentos si no fueron provistos
        if self.text_size == 0:
            self._init_segments()

        # Aplicar probabilidades según tipo de proceso
        self._apply_type_profile()

    def _init_segments(self) -> None:
        """
        Divide la memoria total en segmentos TEXT/DATA/HEAP/STACK.
        Proporciones basadas en la distribución típica de un proceso ELF:
          TEXT  ≈ 40%  (instrucciones del programa)
          DATA  ≈ 30%  (variables inicializadas + BSS)
          HEAP  ≈ 20%  (malloc/dinámica, crece hacia arriba)
          STACK ≈ 10%  (llamadas a funciones, crece hacia abajo)
        """
        t = self.memory_size
        self.text_size  = max(1, int(t * 0.40))
        self.data_size  = max(1, int(t * 0.30))
        self.heap_size  = max(1, int(t * 0.20))
        # El stack toma el resto (evita errores de redondeo)
        self.stack_size = max(1, t - self.text_size - self.data_size - self.heap_size)

    def _apply_type_profile(self) -> None:
        """Aplica las probabilidades de I/O según el tipo de proceso."""
        profile = _TYPE_PROFILES.get(self.process_type, {})
        if profile:
            self.io_probability      = profile["io_probability"]
            self.syscall_probability = profile["syscall_probability"]

    def execute_tick(self) -> None:
        """
        Simula la ejecución de un tick de CPU.
        Avanza el Program Counter y modifica un registro aleatorio.
        Llamado por el engine cuando el proceso está RUNNING.
        """
        # PC avanza entre 4 y 16 bytes (tamaño de instrucción x86 real: 1-15 bytes)
        self.program_counter += random.randint(4, 16)

        # Modificar aleatoriamente un registro (simula operaciones ALU)
        if self.registers:
            reg = random.choice(list(self.registers.keys()))
            # Operación módulo 0xFFFF: simula registros de 16 bits
            self.registers[reg] = (
                self.registers[reg] + random.randint(-100, 100)
            ) & 0xFFFF

    # ── Propiedades calculadas ─────────────────────────────────────────────────

    @property
    def response_time(self) -> int:
        """Tiempo desde llegada hasta PRIMERA ejecución en CPU."""
        if self.start_tick is None:
            return 0
        return self.start_tick - self.arrival_tick

    @property
    def turnaround_time(self) -> int:
        """Tiempo total desde llegada hasta finalización."""
        if self.finish_tick is None:
            return 0
        return self.finish_tick - self.arrival_tick

    @property
    def completion_percent(self) -> float:
        """Porcentaje de completitud (0.0 - 100.0)."""
        if self.burst_time == 0:
            return 100.0
        done = self.burst_time - self.remaining_time
        return min(100.0, (done / self.burst_time) * 100.0)

    @property
    def type_label(self) -> str:
        """Etiqueta corta del tipo de proceso para la UI."""
        labels = {
            ProcessType.CPU_BOUND:   "CPU",
            ProcessType.IO_BOUND:    "I/O",
            ProcessType.INTERACTIVE: "INT",
            ProcessType.SYSTEM:      "SYS",
        }
        return labels.get(self.process_type, "???")
