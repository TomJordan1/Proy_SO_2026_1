"""
iodev/io_manager.py — Gestor de Entrada/Salida.

El IOManager es el punto de contacto entre el engine y los dispositivos.
Coordina las colas de cada dispositivo y notifica al engine cuando
un proceso completó su I/O.

Responsabilidades:
  1. Mantener el registro de todos los dispositivos disponibles
  2. Enrutar solicitudes de I/O al dispositivo correcto
  3. Avanzar (tick) todos los dispositivos en cada tick del engine
  4. Retornar procesos que completaron su I/O (para volver a READY)

Arquitectura:
  Engine → io_manager.enqueue(pcb, "DISK")    → DiskDevice.enqueue(pcb)
  Engine → io_manager.tick()                  → [dev.tick() for each dev]
  Engine ← io_manager.tick() returns [pcb]    ← DiskDevice.tick() = pcb
  Engine → pcb.state = READY, scheduler.add(pcb)
"""

from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

from .devices import Device, KeyboardDevice, DiskDevice, PrinterDevice

if TYPE_CHECKING:
    from core.models import PCB


class IOManager:
    """
    Gestor central de dispositivos de Entrada/Salida.

    Registra todos los dispositivos y coordina sus operaciones
    de manera transparente para el engine.

    Para agregar nuevos dispositivos:
        1. Crear una clase que herede de Device en devices.py
        2. Agregarla al diccionario _devices en __init__
        ¡Sin modificar el engine ni el IOManager!
    """

    def __init__(self):
        # Registro de dispositivos disponibles
        # Clave: nombre del dispositivo (mismo que usa InterruptType)
        self._devices: Dict[str, Device] = {
            "KEYBOARD": KeyboardDevice(),
            "DISK":     DiskDevice(),
            "PRINTER":  PrinterDevice(),
        }

    # ── Operaciones principales ───────────────────────────────────────────────

    def enqueue(self, pcb: PCB, device_name: str) -> bool:
        """
        Encola un proceso en el dispositivo especificado.

        El proceso ya debe estar en estado WAITING (establecido por el engine).
        Este método solo gestiona la cola del dispositivo para visualización
        y control del tiempo de servicio.

        Args:
            pcb        : Proceso que solicita I/O
            device_name: Nombre del dispositivo ("KEYBOARD", "DISK", "PRINTER")

        Returns:
            True si el dispositivo existe, False si no.
        """
        device = self._devices.get(device_name)
        if device is None:
            return False
        device.enqueue(pcb)
        return True

    def tick(self) -> List[PCB]:
        """
        Avanza TODOS los dispositivos un tick.

        Retorna la lista de procesos que completaron su I/O en este tick.
        El engine los moverá de WAITING → READY.

        Returns:
            Lista de PCBs (puede estar vacía si nadie terminó I/O)
        """
        completed: List[PCB] = []
        for device in self._devices.values():
            result = device.tick()
            if result is not None:
                completed.append(result)
        return completed

    # ── Consultas ─────────────────────────────────────────────────────────────

    def get_device(self, name: str) -> Optional[Device]:
        """Retorna un dispositivo por nombre."""
        return self._devices.get(name)

    def get_all_devices(self) -> Dict[str, Device]:
        """Retorna todos los dispositivos (para visualización)."""
        return self._devices

    def status_snapshot(self) -> List[Dict]:
        """
        Retorna el estado de todos los dispositivos para la UI.

        Formato de cada dispositivo:
          {
            "name"         : "DISK",
            "icon"         : "💾",
            "busy"         : True,
            "current"      : "P3",   (proceso siendo atendido)
            "queue_length" : 2,
            "total_served" : 7,
            "ticks_rem"    : 5,
          }
        """
        result = []
        for name, device in self._devices.items():
            result.append({
                "name":          name,
                "icon":          device.icon,
                "busy":          device.is_busy,
                "current":       device.current_process_name,
                "queue_length":  device.queue_length,
                "total_served":  device.total_served,
                "ticks_rem":     device.ticks_remaining,
            })
        return result

    # ── Control ───────────────────────────────────────────────────────────────

    def remove_process(self, pcb: PCB) -> None:
        """
        Remueve un proceso de TODOS los dispositivos.
        (Cuando el proceso es terminado forzosamente)
        """
        for device in self._devices.values():
            device.remove_process(pcb)

    def reset(self) -> None:
        """Reinicia todos los dispositivos."""
        for device in self._devices.values():
            device.reset()
