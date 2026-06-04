"""
kernel/io/manager.py — Gestor de Dispositivos de Entrada/Salida.

Coordina los 5 dispositivos del sistema (KEYBOARD, DISK, PRINTER, NETWORK, USB).
En cada tick:
    1. Avanza el servicio de cada dispositivo (device.tick())
    2. Retorna los procesos que completaron I/O (deben volver a READY)

Integración con interrupciones:
    - Cuando el engine decide que un proceso va a I/O:
        engine → io_manager.request(pcb, device_name)
        el PCB pasa a state=WAITING + io_device=device_name

    - Cuando el dispositivo termina:
        io_manager.tick() → retorna lista de PCBs completados
        engine → pone cada PCB en state=READY y lo manda al scheduler
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .device import Device, DeviceName
from ..models.pcb import PCB, ProcessState


class IOManager:
    """
    Gestor centralizado de todos los dispositivos I/O.

    El engine interactúa exclusivamente con esta clase.
    """

    def __init__(self, latencies: Optional[Dict[str, int]] = None) -> None:
        """
        Args:
            latencies: Dict {device_name: latency_ticks} desde HardwareConfig.
                       Si None, se usan valores por defecto.
        """
        lat = latencies or {}
        self.devices: Dict[str, Device] = {
            DeviceName.KEYBOARD.value: Device(DeviceName.KEYBOARD, lat.get("KEYBOARD", 7)),
            DeviceName.DISK.value:     Device(DeviceName.DISK,     lat.get("DISK",     15)),
            DeviceName.PRINTER.value:  Device(DeviceName.PRINTER,  lat.get("PRINTER",  20)),
            DeviceName.NETWORK.value:  Device(DeviceName.NETWORK,  lat.get("NETWORK",  30)),
            DeviceName.USB.value:      Device(DeviceName.USB,      lat.get("USB",      12)),
        }

    def request(self, pcb: PCB, device_name: str, current_tick: int) -> bool:
        """
        Registra una solicitud de I/O para el proceso `pcb`.

        Pone el proceso en WAITING y lo encola en el dispositivo.

        Args:
            pcb        : Proceso que solicita I/O
            device_name: Nombre del dispositivo ("DISK", "KEYBOARD", etc.)
            current_tick: Tick actual

        Returns:
            True si el dispositivo aceptó la solicitud, False si cola llena.
        """
        device = self.devices.get(device_name)
        if not device:
            return False

        pcb.state = ProcessState.WAITING
        pcb.io_device = device_name
        pcb.io_remaining = device.latency

        return device.enqueue(pcb, current_tick)

    def tick(self) -> List[PCB]:
        """
        Avanza todos los dispositivos un tick.

        Returns:
            Lista de PCBs cuyos I/O terminaron este tick.
            El engine debe devolverlos a READY.
        """
        completed: List[PCB] = []
        for device in self.devices.values():
            done = device.tick()
            if done is not None:
                done.io_device = None
                done.io_remaining = 0
                completed.append(done)
        return completed

    def get_all_status(self) -> List[dict]:
        """Retorna el estado de todos los dispositivos para la UI."""
        return [d.get_status_snapshot() for d in self.devices.values()]

    def get_waiting_processes(self) -> List[PCB]:
        """Lista de todos los PCBs actualmente en colas de I/O."""
        waiting = []
        for device in self.devices.values():
            if device.current:
                waiting.append(device.current.pcb)
            for req in device.queue:
                waiting.append(req.pcb)
        return waiting

    def update_latencies(self, latencies: Dict[str, int]) -> None:
        """Actualiza las latencias de los dispositivos en caliente."""
        for name, lat in latencies.items():
            if name in self.devices:
                self.devices[name].latency = lat

    def reset(self) -> None:
        """Reinicia todos los dispositivos."""
        for device in self.devices.values():
            device.reset()
