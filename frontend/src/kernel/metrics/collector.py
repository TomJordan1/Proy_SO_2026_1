"""
kernel/metrics/collector.py — Recolector de Métricas del Sistema.

Calcula métricas REALES emergentes de la simulación (req1.txt):
    - CPU utilization   : % de ticks en que al menos un core estuvo ocupado
    - Throughput        : procesos completados por cada 100 ticks
    - Turnaround time   : (finish_tick - arrival_tick) por proceso
    - Waiting time      : ticks en READY sin ejecutar
    - Response time     : (start_tick - arrival_tick) por proceso
    - Fragmentation     : emerge del MemoryManager
    - Starvation events : conteo de aging aplicados
    - Context switches  : total de cambios de contexto

Impacto del hardware (req2.txt) — ejemplos verificables:
    - más CPUs      → mayor throughput
    - menor RAM     → más fragmentación → procesos rechazados
    - disco lento   → mayor avg_waiting_time
    - quantum corto → más context_switches
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.pcb import PCB


@dataclass
class ProcessMetrics:
    """Métricas individuales de un proceso completado."""
    pid:            int
    name:           str
    process_type:   str
    burst_time:     int
    turnaround:     int
    waiting_time:   int
    response_time:  int
    exit_code:      int


class MetricsCollector:
    """
    Recolector global de métricas de la simulación.

    El engine llama a los métodos de este objeto en cada tick y al
    finalizar cada proceso. La UI lee las propiedades calculadas.
    """

    def __init__(self, num_cpus: int = 1) -> None:
        self.num_cpus: int = num_cpus

        # Contadores de CPU
        self.total_ticks: int = 0
        self.cpu_busy_ticks: int = 0       # Ticks con al menos 1 core ocupado
        self.cpu_idle_ticks: int = 0

        # Procesos
        self.total_created: int = 0
        self.total_completed: int = 0
        self.total_errors: int = 0
        self.total_rejected: int = 0       # Sin memoria al crear

        # Métricas de procesos completados
        self.completed_records: List[ProcessMetrics] = []

        # Context switches
        self.context_switches: int = 0
        self.switch_overhead_ticks: int = 0

        # Starvation
        self.starvation_events: int = 0

        # Interrupciones por tipo
        self.interrupts_by_type: dict = {}

    # ── Actualizaciones por tick ──────────────────────────────────────────────

    def record_tick(self, active_cores: int) -> None:
        """
        Llamado al final de cada tick.

        Args:
            active_cores: Número de cores con proceso RUNNING este tick.
        """
        self.total_ticks += 1
        if active_cores > 0:
            self.cpu_busy_ticks += 1
        else:
            self.cpu_idle_ticks += 1

    def record_completion(self, pcb: "PCB") -> None:
        """Llamado cuando un proceso termina (TERMINATED)."""
        self.total_completed += 1
        if pcb.exit_code != 0:
            self.total_errors += 1

        self.completed_records.append(ProcessMetrics(
            pid=pcb.pid,
            name=pcb.name,
            process_type=str(pcb.process_type.value),
            burst_time=pcb.burst_time,
            turnaround=pcb.turnaround_time,
            waiting_time=pcb.waiting_time,
            response_time=pcb.response_time,
            exit_code=pcb.exit_code,
        ))

    def record_context_switch(self, overhead_ticks: int) -> None:
        self.context_switches += 1
        self.switch_overhead_ticks += overhead_ticks

    def record_starvation(self) -> None:
        self.starvation_events += 1

    def record_rejection(self) -> None:
        """Proceso rechazado por falta de memoria."""
        self.total_rejected += 1

    def record_interrupt(self, interrupt_type: str) -> None:
        self.interrupts_by_type[interrupt_type] = (
            self.interrupts_by_type.get(interrupt_type, 0) + 1
        )

    # ── Propiedades calculadas ────────────────────────────────────────────────

    @property
    def cpu_utilization(self) -> float:
        """Porcentaje de tiempo en que la CPU estuvo activa (0-100)."""
        if self.total_ticks == 0:
            return 0.0
        return (self.cpu_busy_ticks / self.total_ticks) * 100.0

    @property
    def throughput(self) -> float:
        """Procesos completados por cada 100 ticks."""
        if self.total_ticks == 0:
            return 0.0
        return (self.total_completed / self.total_ticks) * 100.0

    @property
    def avg_turnaround(self) -> float:
        """Tiempo promedio de retorno (ticks)."""
        if not self.completed_records:
            return 0.0
        return sum(r.turnaround for r in self.completed_records) / len(self.completed_records)

    @property
    def avg_waiting(self) -> float:
        """Tiempo promedio de espera (ticks)."""
        if not self.completed_records:
            return 0.0
        return sum(r.waiting_time for r in self.completed_records) / len(self.completed_records)

    @property
    def avg_response(self) -> float:
        """Tiempo promedio de respuesta (ticks)."""
        if not self.completed_records:
            return 0.0
        return sum(r.response_time for r in self.completed_records) / len(self.completed_records)

    @property
    def error_rate(self) -> float:
        """Porcentaje de procesos que terminaron con error."""
        if self.total_completed == 0:
            return 0.0
        return (self.total_errors / self.total_completed) * 100.0

    def get_snapshot(self) -> dict:
        """Retorna un diccionario con todas las métricas para la UI."""
        return {
            "cpu_utilization":    round(self.cpu_utilization, 1),
            "throughput":         round(self.throughput, 2),
            "avg_turnaround":     round(self.avg_turnaround, 1),
            "avg_waiting":        round(self.avg_waiting, 1),
            "avg_response":       round(self.avg_response, 1),
            "total_created":      self.total_created,
            "total_completed":    self.total_completed,
            "total_errors":       self.total_errors,
            "total_rejected":     self.total_rejected,
            "context_switches":   self.context_switches,
            "switch_overhead_t":  self.switch_overhead_ticks,
            "starvation_events":  self.starvation_events,
            "error_rate":         round(self.error_rate, 1),
            "interrupts":         dict(self.interrupts_by_type),
        }

    def reset(self) -> None:
        """Reinicia todas las métricas."""
        self.__init__(self.num_cpus)
