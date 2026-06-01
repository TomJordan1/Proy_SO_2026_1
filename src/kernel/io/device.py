"""
kernel/io/device.py — Modelos de Dispositivos de Entrada/Salida.

Cada dispositivo tiene:
    - Cola FIFO de solicitudes pendientes (PCBs en WAITING)
    - Estado: BUSY (atendiendo) / FREE (disponible)
    - Latencia configurable (en ticks)
    - Historial de solicitudes atendidas

Las interrupciones I/O NO son puramente aleatorias (req1.txt):
    - La solicitud emerge de io_probability del proceso
    - La duración depende de la latencia configurada del dispositivo
    - La compleción genera una interrupción IO_COMPLETE al engine

Dispositivos soportados:
    KEYBOARD  — interacción de usuario (latencia baja)
    DISK      — lectura/escritura de archivos (latencia media)
    PRINTER   — impresión de documentos (latencia alta)
    NETWORK   — comunicación de red (latencia variable, alta)
    USB       — transferencia por bus USB (latencia media-baja)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from ..models.pcb import PCB


class DeviceName(str, Enum):
    """Nombres de los dispositivos disponibles."""
    KEYBOARD = "KEYBOARD"
    DISK     = "DISK"
    PRINTER  = "PRINTER"
    NETWORK  = "NETWORK"
    USB      = "USB"


@dataclass
class IORequest:
    """Solicitud de I/O pendiente en la cola de un dispositivo."""
    pcb:             PCB
    duration:        int     # Ticks de servicio (basado en latencia del dispositivo)
    remaining:       int     # Ticks restantes de atención
    arrival_tick:    int     # Cuando llegó a la cola del dispositivo

    def __post_init__(self):
        if self.remaining == 0:
            self.remaining = self.duration


class Device:
    """
    Dispositivo de I/O simulado con cola propia.

    Cada tick, el device avanza el servicio del request actual.
    Cuando termina, retorna el PCB para que vuelva a READY.
    """

    def __init__(self, name: DeviceName, latency: int = 10, queue_max: int = 10) -> None:
        self.name: DeviceName = name
        self.latency: int = latency
        """Ticks base de servicio. Configurable desde HardwareConfig."""

        self.queue_max: int = queue_max
        """Máximo de solicitudes en cola simultáneas."""

        self.queue: List[IORequest] = []
        """Cola FIFO de solicitudes pendientes (excluye la actual)."""

        self.current: Optional[IORequest] = None
        """Solicitud actualmente en servicio (None si IDLE)."""

        self.total_served: int = 0
        """Total de solicitudes atendidas (para métricas)."""

        self.total_wait_ticks: int = 0
        """Ticks totales acumulados en la cola (avg wait = total/served)."""

    @property
    def is_busy(self) -> bool:
        return self.current is not None

    @property
    def queue_length(self) -> int:
        return len(self.queue)

    @property
    def progress_percent(self) -> float:
        """Porcentaje de servicio del request actual (para la UI)."""
        if not self.current:
            return 0.0
        done = self.current.duration - self.current.remaining
        return (done / self.current.duration) * 100.0 if self.current.duration > 0 else 0.0

    def enqueue(self, pcb: PCB, arrival_tick: int) -> bool:
        """
        Encola una solicitud de I/O del proceso `pcb`.

        Args:
            pcb         : Proceso que solicita I/O
            arrival_tick: Tick actual (para métricas de wait)

        Returns:
            True si fue encolada, False si la cola está llena.
        """
        if len(self.queue) >= self.queue_max:
            return False   # Cola llena: la solicitud es descartada

        req = IORequest(
            pcb=pcb,
            duration=self.latency,
            remaining=self.latency,
            arrival_tick=arrival_tick,
        )

        if not self.is_busy:
            # El dispositivo está libre: atender directamente
            self.current = req
        else:
            # El dispositivo está ocupado: encolar
            self.queue.append(req)
        return True

    def tick(self) -> Optional[PCB]:
        """
        Avanza un tick de servicio del dispositivo.

        Returns:
            El PCB que terminó su I/O (para que el engine lo devuelva a READY),
            o None si no hay ningún proceso terminado este tick.
        """
        if not self.current:
            # Tomar el siguiente de la cola
            if self.queue:
                self.current = self.queue.pop(0)
                self.total_wait_ticks += (
                    self.current.remaining - self.current.arrival_tick
                )
            return None

        # Decrementar tiempo restante
        self.current.remaining -= 1

        if self.current.remaining <= 0:
            # Solicitud completada
            done_pcb = self.current.pcb
            self.current = None
            self.total_served += 1

            # Atender el siguiente inmediatamente
            if self.queue:
                self.current = self.queue.pop(0)

            return done_pcb   # El engine lo devolverá a READY

        return None

    def get_status_snapshot(self) -> dict:
        """Resumen del estado para la UI."""
        return {
            "name":          self.name.value,
            "is_busy":       self.is_busy,
            "queue_length":  self.queue_length,
            "total_served":  self.total_served,
            "latency":       self.latency,
            "progress":      self.progress_percent,
            "current_pid":   self.current.pcb.pid if self.current else None,
            "current_name":  self.current.pcb.name if self.current else None,
            "queue_pids":    [r.pcb.pid for r in self.queue],
        }

    def reset(self) -> None:
        """Reinicia el dispositivo para reset de simulación."""
        self.queue.clear()
        self.current = None
        self.total_served = 0
        self.total_wait_ticks = 0
