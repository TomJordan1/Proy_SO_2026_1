"""
metrics/metrics.py — Recolección y Cálculo de Métricas de Rendimiento.

Las métricas permiten EVALUAR y COMPARAR algoritmos de scheduling.
Son fundamentales para el análisis académico del simulador.

Métricas implementadas:
  ┌──────────────────────┬─────────────────────────────────────────────────┐
  │ Métrica              │ Fórmula                                         │
  ├──────────────────────┼─────────────────────────────────────────────────┤
  │ CPU Utilization      │ (ticks_CPU_ocupada / ticks_total) × 100         │
  │ Throughput           │ procesos_completados / ticks_total              │
  │ Avg Waiting Time     │ Σ(waiting_time_i) / N_terminados                │
  │ Avg Response Time    │ Σ(start_tick_i - arrival_tick_i) / N_terminados │
  │ Avg Turnaround Time  │ Σ(finish_tick_i - arrival_tick_i) / N_terminados│
  └──────────────────────┴─────────────────────────────────────────────────┘

Interpretación para comparar FCFS vs Round Robin:
  - FCFS suele tener mejor throughput (menos context switches)
  - RR suele tener mejor avg_response_time (todos ejecutan pronto)
  - Con procesos largos, FCFS tiene peor avg_waiting_time (convoy effect)
  - Ninguno es "mejor" en todo → depende del caso de uso
"""

from __future__ import annotations

from typing import Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import PCB


class MetricsCollector:
    """
    Recolector de métricas de rendimiento.

    Se actualiza en cada tick del engine.
    Proporciona cálculos en tiempo real para la UI.
    """

    def __init__(self):
        # Contadores de ticks de CPU
        self.total_ticks:  int = 0  # Ticks totales transcurridos
        self.busy_ticks:   int = 0  # Ticks con proceso en CPU
        self.idle_ticks:   int = 0  # Ticks con CPU ociosa

        # Contadores de procesos
        self.total_created:   int = 0  # Procesos creados (incluye los del SO)
        self.total_completed: int = 0  # Terminados normalmente (exit_code=0)
        self.total_errors:    int = 0  # Terminados con error (exit_code!=0)

        # Acumuladores para calcular promedios
        # Se suman los valores de cada proceso al terminar
        self._sum_waiting:    int = 0
        self._sum_response:   int = 0
        self._sum_turnaround: int = 0

        # Conjunto de PIDs ya procesados (para no contar dos veces)
        self._counted_pids: set = set()

    def update(self, tick: int, cpu_busy: bool, all_processes: List[PCB]) -> None:
        """
        Actualiza las métricas en cada tick.

        Llamar una vez por tick desde el engine.

        Args:
            tick        : Número de tick actual
            cpu_busy    : True si hay un proceso en RUNNING
            all_processes: Lista de todos los procesos (para detectar terminados)
        """
        from core.models import ProcessState

        self.total_ticks = tick

        # Actualizar contadores de CPU
        if cpu_busy:
            self.busy_ticks += 1
        else:
            self.idle_ticks += 1

        # Detectar procesos recién terminados y acumular sus métricas
        for pcb in all_processes:
            if (pcb.state == ProcessState.TERMINATED
                    and pcb.finish_tick == tick
                    and pcb.pid not in self._counted_pids):

                # Marcar como contado para no procesarlo de nuevo
                self._counted_pids.add(pcb.pid)

                # Clasificar por tipo de terminación
                if pcb.exit_code == 0:
                    self.total_completed += 1
                else:
                    self.total_errors += 1

                # Acumular para promedios
                self._sum_waiting    += pcb.waiting_time
                self._sum_response   += pcb.response_time
                self._sum_turnaround += pcb.turnaround_time

    # ── Cálculos ──────────────────────────────────────────────────────────────

    def cpu_utilization(self) -> float:
        """
        Porcentaje de tiempo que la CPU estuvo ocupada.

        100% = CPU siempre ocupada (ideal para batch systems)
        0%   = CPU siempre ociosa (sin procesos)

        Un valor alto no siempre es bueno: si todo el tiempo se usa
        en context switches, la CPU está "ocupada" pero improductiva.
        """
        if self.total_ticks == 0:
            return 0.0
        return (self.busy_ticks / self.total_ticks) * 100.0

    def throughput(self) -> float:
        """
        Procesos completados por tick.

        Mayor throughput = el sistema procesa más trabajo por unidad de tiempo.
        FCFS suele tener mejor throughput que RR por el menor overhead.
        """
        if self.total_ticks == 0:
            return 0.0
        return self.total_completed / self.total_ticks

    def avg_waiting_time(self) -> float:
        """
        Tiempo promedio que un proceso esperó en la cola READY.

        Mide la "justicia" del scheduler:
          - FCFS con procesos largos primero: waiting_time alto para los cortos
          - RR: waiting_time más uniforme entre todos los procesos
        """
        n = self.total_completed + self.total_errors
        if n == 0:
            return 0.0
        return self._sum_waiting / n

    def avg_response_time(self) -> float:
        """
        Tiempo promedio desde llegada hasta PRIMERA ejecución en CPU.

        Importante para sistemas interactivos:
          - El usuario quiere que su proceso comience pronto
          - RR garantiza que todos ejecutan en el primer quantum
          - FCFS puede tener response_time alto (si hay procesos largos antes)
        """
        n = self.total_completed + self.total_errors
        if n == 0:
            return 0.0
        return self._sum_response / n

    def avg_turnaround_time(self) -> float:
        """
        Tiempo promedio desde llegada hasta finalización completa.

        Incluye: espera + ejecución + I/O.
        Métrica más completa del rendimiento percibido por el usuario.
        """
        n = self.total_completed + self.total_errors
        if n == 0:
            return 0.0
        return self._sum_turnaround / n

    # ── Resumen ───────────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        """
        Retorna todas las métricas como diccionario.

        Usado por la UI para actualizar el panel de métricas.
        """
        return {
            "cpu_utilization":    round(self.cpu_utilization(), 1),
            "throughput":         round(self.throughput(), 4),
            "avg_waiting_time":   round(self.avg_waiting_time(), 1),
            "avg_response_time":  round(self.avg_response_time(), 1),
            "avg_turnaround_time":round(self.avg_turnaround_time(), 1),
            "total_created":      self.total_created,
            "total_completed":    self.total_completed,
            "total_errors":       self.total_errors,
            "busy_ticks":         self.busy_ticks,
            "idle_ticks":         self.idle_ticks,
        }

    def reset(self) -> None:
        """Reinicia todos los contadores."""
        self.__init__()
