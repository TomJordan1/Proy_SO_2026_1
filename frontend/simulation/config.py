"""
simulation/config.py — Configuración de Hardware del Sistema Simulado.

HardwareConfig es el modelo central para el diálogo de configuración.
Esta estructura se serializa en `escenario_modelo.json` para que el 
futuro Motor de Simulación (Backend en C++) lo lea y aplique las reglas físicas.

Diseño:
    - Un único dataclass con todos los parámetros del hardware
    - Se crea y configura en la Interfaz Gráfica (ConfigDialog)
    - Al aceptar o modificar, se exporta al JSON.
    - El backend C++ consumirá este archivo para calcular `output_modelo.json`.

Impacto real de parámetros (req2.txt):
    - num_cpus      → más throughput, más context switches
    - total_mem_mb  → menos RAM → más fragmentación, procesos rechazados
    - disk_latency  → I/O más lento → más waiting_time
    - quantum       → quantum pequeño → más context switches, mejor resp.
    - aging_interval → anti-starvation configurable
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class HardwareConfig:
    """
    Configuración completa del hardware simulado.

    Todos los parámetros son configurables desde la UI antes de iniciar
    la simulación. El engine NO tiene valores hardcodeados; usa esta clase.
    """

    # ── CPU ───────────────────────────────────────────────────────────────────
    num_cpus: int = 1
    """Número de cores (1-4). Cada core tiene su propio scheduler."""

    quantum_default: int = 4
    """Ticks por quantum para RR/Priority-RR. Configurable por core."""

    context_switch_cost: int = 1
    """Ticks de overhead por cambio de contexto. 0 = instantáneo."""

    scheduler_algorithm: str = "FCFS"
    """Algoritmo inicial: FCFS, SJF, SRTF, Priority, RR, MLFQ(futuro)."""

    preemptive: bool = True
    """Si el scheduler puede expulsar el proceso en CPU."""

    # ── Memoria ───────────────────────────────────────────────────────────────
    total_memory_mb: int = 1024
    """RAM total del sistema simulado (MB)."""

    min_segment_mb: int = 4
    """Tamaño mínimo de segmento libre para que sea utilizable."""

    max_process_mb: int = 256
    """Tamaño máximo de memoria que puede pedir un proceso."""

    alloc_strategy: str = "first"
    """Estrategia: 'first' (First Fit), 'best' (Best Fit), 'worst' (Worst Fit)."""

    mmu_enabled: bool = True
    """
    Si la MMU abstracta está activa.
    Cuando True: muestra traducción lógica→física en la UI.
    Extensibilidad: en versión futura, activar 'virtual_memory_enabled'
    cambiará la MMU de SegmentMMU a PagedMMU sin modificar el engine.
    """

    virtual_memory_enabled: bool = False
    """
    RESERVADO — Paginación virtual (no implementada aún).
    Preparado para integración futura. Cuando se active:
      - MemoryManager usará PagedMemoryManager en lugar de SegmentMMU
      - La UI mostrará tabla de páginas y TLB
    """

    # ── Dispositivos I/O ──────────────────────────────────────────────────────
    keyboard_latency: int = 7
    """Ticks para atender una solicitud de teclado."""

    disk_latency: int = 15
    """Ticks para atender una operación de disco (seek + transfer)."""

    printer_latency: int = 20
    """Ticks para imprimir un trabajo."""

    network_latency: int = 30
    """Ticks para una operación de red (RTT simulado)."""

    usb_latency: int = 12
    """Ticks para transferencia USB."""

    device_queue_max: int = 10
    """Tamaño máximo de la cola por dispositivo."""

    # ── Simulación ────────────────────────────────────────────────────────────
    sim_speed_ms: int = 800
    """Milisegundos entre ticks (mayor = más lento). Rango: 80-2000."""

    error_probability: float = 0.005
    """Probabilidad de que un proceso sufra un error fatal (0.0-1.0)."""

    io_freq_multiplier: float = 1.0
    """
    Multiplicador de frecuencia de I/O.
    1.0 = valores base por proceso_type.
    2.0 = el doble de solicitudes I/O.
    0.5 = la mitad.
    """

    interrupt_freq: float = 0.02
    """Probabilidad de interrupción de timer global por tick (0.0-1.0)."""

    aging_enabled: bool = True
    """Si el aging anti-starvation está activo."""

    aging_interval: int = 20
    """Cada cuántos ticks en READY se incrementa prioridad (anti-starvation)."""

    # ── Procesos ──────────────────────────────────────────────────────────────
    auto_create: bool = True
    """Si el sistema crea procesos automáticamente durante la simulación."""

    max_ticks: int = 0
    """
    Límite de ticks para la simulación (0 = sin límite).
    Cuando auto_create=True y este valor > 0, el engine deja de crear
    nuevos procesos al alcanzar este tick, permitiendo que la simulación
    termine naturalmente cuando todos los procesos existentes finalicen.
    """

    initial_processes: int = 10
    """Número de procesos a cargar al inicio (0 si es modo manual)."""

    cpu_bound_ratio: float = 0.40
    """Proporción de procesos CPU-bound (el resto es IO-bound/INTERACTIVE)."""

    use_system_processes: bool = True
    """Si se cargan procesos reales del SO (psutil)."""

    # ── Propiedades derivadas ─────────────────────────────────────────────────

    def device_latencies(self) -> Dict[str, int]:
        """Diccionario nombre→latencia para todos los dispositivos."""
        return {
            "KEYBOARD": self.keyboard_latency,
            "DISK":     self.disk_latency,
            "PRINTER":  self.printer_latency,
            "NETWORK":  self.network_latency,
            "USB":      self.usb_latency,
        }

    def effective_io_probability(self, base_prob: float) -> float:
        """Aplica el multiplicador de I/O a la probabilidad base del proceso."""
        return min(0.95, base_prob * self.io_freq_multiplier)
