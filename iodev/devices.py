"""
iodev/devices.py — Simulación de Dispositivos de Entrada/Salida.

Los dispositivos de E/S son recursos del sistema que los procesos solicitan
para realizar operaciones como leer del teclado, escribir en disco, etc.

Flujo de I/O en el simulador:
  1. Proceso en RUNNING solicita I/O (via interrupción IO_REQUEST)
  2. Proceso pasa a WAITING
  3. Dispositivo lo encola en su cola propia
  4. Dispositivo atiende de a uno por vez (modelo serie simplificado)
  5. Cuando termina el servicio, el proceso puede volver a READY

Dispositivos implementados:
  ┌──────────┬──────────────────────────────────┬───────────────┐
  │ Nombre   │ Descripción                      │ Tiempo serv.  │
  ├──────────┼──────────────────────────────────┼───────────────┤
  │ KEYBOARD │ Captura de teclado               │ 5-10 ticks    │
  │ DISK     │ Lectura/escritura en disco       │ 10-20 ticks   │
  │ PRINTER  │ Cola de impresión                │ 15-25 ticks   │
  └──────────┴──────────────────────────────────┴───────────────┘

En un SO real:
  - Cada dispositivo tiene su driver (controlador)
  - Las interrupciones de hardware notifican cuando el I/O completa
  - DMA (Direct Memory Access) permite I/O sin ocupar la CPU

Aquí simplificamos: cada dispositivo tiene un contador de ticks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import PCB


# ─────────────────────────────────────────────────────────────────────────────
# Clase base — Device
# ─────────────────────────────────────────────────────────────────────────────

class Device(ABC):
    """
    Clase base para todos los dispositivos de E/S.

    Características de cada dispositivo:
      - Cola propia FIFO: múltiples procesos pueden esperar
      - Atiende UN proceso por vez (ocupado/libre)
      - Tiempo de servicio fijo (simplificación educativa)
      - Estadísticas: total de procesos atendidos

    Args:
        name        : Nombre del dispositivo ("KEYBOARD", etc.)
        service_time: Ticks para atender un proceso
    """

    def __init__(self, name: str, service_time: int):
        self.name: str = name
        self.service_time: int = service_time

        # Cola FIFO de procesos esperando este dispositivo
        self._queue: deque[PCB] = deque()

        # Proceso que está siendo atendido actualmente
        self._current_pcb: Optional[PCB] = None

        # Ticks restantes de servicio para el proceso actual
        self._ticks_remaining: int = 0

        # Estadística: total de procesos atendidos por este dispositivo
        self.total_served: int = 0

    # ── Propiedades ───────────────────────────────────────────────────────────

    @property
    def is_busy(self) -> bool:
        """True si el dispositivo está atendiendo a algún proceso."""
        return self._current_pcb is not None

    @property
    def queue_length(self) -> int:
        """Número de procesos esperando (sin contar el que se atiende)."""
        return len(self._queue)

    @property
    def current_process_name(self) -> str:
        """Nombre del proceso siendo atendido (o '--' si idle)."""
        return self._current_pcb.name if self._current_pcb else "--"

    @property
    def ticks_remaining(self) -> int:
        """Ticks restantes para completar el servicio actual."""
        return self._ticks_remaining

    # ── Operaciones ───────────────────────────────────────────────────────────

    def enqueue(self, pcb: PCB) -> None:
        """
        Registra una solicitud de I/O de un proceso.

        El proceso se encola para ser atendido.
        Si el dispositivo está libre, comenzará a atenderlo inmediatamente.

        Note: El estado del proceso (WAITING) ya fue establecido por el engine.
        Este método solo gestiona la cola del dispositivo.
        """
        self._queue.append(pcb)
        # Si el dispositivo estaba libre, empezar a atender
        if not self.is_busy:
            self._start_next()

    def tick(self) -> Optional[PCB]:
        """
        Avanza un tick el dispositivo.

        Si el dispositivo está atendiendo un proceso:
          - Decrementa el tiempo restante
          - Si llega a 0: el proceso terminó su I/O, retornarlo

        Returns:
            El PCB que completó su I/O (el engine lo moverá a READY),
            o None si nadie terminó en este tick.
        """
        if not self.is_busy:
            self._start_next()
            return None

        self._ticks_remaining -= 1

        if self._ticks_remaining <= 0:
            # ¡I/O completado! Retornar el proceso para que vuelva a READY
            completed = self._current_pcb
            self._current_pcb = None
            self._ticks_remaining = 0
            self.total_served += 1

            # Atender el siguiente proceso en la cola (si hay)
            self._start_next()

            return completed

        return None

    def remove_process(self, pcb: PCB) -> None:
        """
        Remueve un proceso de la cola del dispositivo.
        (Útil si el proceso fue terminado mientras esperaba I/O)
        """
        try:
            self._queue.remove(pcb)
        except ValueError:
            pass
        # Si era el proceso actual, cancelar
        if self._current_pcb == pcb:
            self._current_pcb = None
            self._ticks_remaining = 0
            self._start_next()

    def queue_snapshot(self) -> List[PCB]:
        """
        Retorna una lista de todos los procesos asociados al dispositivo:
        el proceso siendo atendido + los que esperan en la cola.

        Usado por la UI para visualizar las colas de cada dispositivo.
        """
        result: List[PCB] = []
        if self._current_pcb:
            result.append(self._current_pcb)
        result.extend(list(self._queue))
        return result

    def reset(self) -> None:
        """Reinicia el estado del dispositivo."""
        self._queue.clear()
        self._current_pcb = None
        self._ticks_remaining = 0
        self.total_served = 0

    # ── Privado ───────────────────────────────────────────────────────────────

    def _start_next(self) -> None:
        """Comienza a atender el siguiente proceso en la cola."""
        if self._queue and not self.is_busy:
            self._current_pcb = self._queue.popleft()
            self._ticks_remaining = self.service_time

    @property
    @abstractmethod
    def icon(self) -> str:
        """Ícono Unicode para mostrar en la UI."""
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Dispositivos concretos
# ─────────────────────────────────────────────────────────────────────────────

class KeyboardDevice(Device):
    """
    Teclado — Dispositivo de entrada más rápido.

    Simula la captura de input del usuario (keypress, scan codes).
    Tiempo de servicio corto: el hardware de teclado responde rápido.
    """

    def __init__(self):
        super().__init__("KEYBOARD", service_time=7)

    @property
    def icon(self) -> str:
        return "⌨"


class DiskDevice(Device):
    """
    Disco — Almacenamiento secundario.

    Simula acceso a archivos en disco (seek time + transfer time).
    Tiempo de servicio medio: el disco mecánico tiene latencia alta.
    (SSD sería más rápido, pero usamos HDD como modelo educativo)
    """

    def __init__(self):
        super().__init__("DISK", service_time=15)

    @property
    def icon(self) -> str:
        return "💾"


class PrinterDevice(Device):
    """
    Impresora — Dispositivo de salida más lento.

    Simula una cola de impresión (print spool).
    Tiempo de servicio largo: las impresoras físicas son lentas.
    """

    def __init__(self):
        super().__init__("PRINTER", service_time=20)

    @property
    def icon(self) -> str:
        return "🖨"
