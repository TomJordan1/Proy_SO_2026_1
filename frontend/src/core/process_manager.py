"""
core/process_manager.py — Gestor del Ciclo de Vida de los Procesos.

El ProcessManager es responsable de:
  1. Crear procesos (desde el sistema real con psutil o manualmente)
  2. Transicionar procesos entre estados
  3. Mantener las colas de admisión (new_queue) y espera (waiting_queue)
  4. Liberar recursos al terminar

Relación con otros módulos:
  - ProcessManager usa MemoryManager para asignar/liberar memoria
  - Engine usa ProcessManager para crear procesos y consultar su estado
  - Scheduler gestiona la cola READY (separación de responsabilidades)
  - IOManager gestiona los dispositivos (el ProcessManager solo marca WAITING)

Carga de procesos del sistema:
  Usa psutil para leer los procesos reales del SO en ejecución.
  Esto hace la simulación más realista y permite:
    - Ver procesos familiares (chrome.exe, explorer.exe, etc.)
    - Entender que el SO siempre tiene procesos en ejecución
    - Comparar con los procesos manuales que el estudiante crea
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from memory.memory_manager import MemoryManager

from .models import PCB, ProcessState, reset_pid_counter
from utils.randomizer import random_burst_time, random_priority, random_memory_size

# Intentar importar psutil (puede no estar instalado en algunos entornos)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class ProcessManager:
    """
    Gestiona el ciclo de vida completo de los procesos.

    Mantiene:
      all_processes : dict PID → PCB con TODOS los procesos (histórico)
      new_queue     : procesos creados, esperando ser admitidos a memoria
      waiting_queue : procesos bloqueados en I/O (estado WAITING)

    La cola READY está en el Scheduler (separación de responsabilidades).
    El Engine conecta los dos: cuando admite un proceso, lo agrega al Scheduler.
    """

    # Nombres de procesos simulados (cuando psutil no está disponible)
    SIMULATED_NAMES = [
        "SystemInit", "KernelTask", "NetManager", "FileSystem",
        "AudioSrv", "DisplayMgr", "InputHandler", "SecuritySvc",
        "MemoryMgr", "TaskSched", "EventLogger", "UpdateSvc",
    ]

    def __init__(self, memory_manager: MemoryManager):
        self.memory: MemoryManager = memory_manager

        # Todos los procesos (incluidos los terminados, para métricas históricas)
        self.all_processes: Dict[int, PCB] = {}

        # Cola de admisión: procesos nuevos esperando memoria
        # (scheduler de largo plazo: controla cuántos entran al sistema)
        self.new_queue: List[PCB] = []

        # Cola de espera: procesos bloqueados por I/O
        self.waiting_queue: List[PCB] = []

        # Contador para auto-nombrar procesos manuales
        self._manual_count: int = 0

    # ── Creación de Procesos ──────────────────────────────────────────────────

    def load_system_processes(self, max_count: int = 10) -> List[PCB]:
        """
        Carga procesos reales del sistema operativo usando psutil.

        Si psutil no está disponible o falla, genera procesos simulados.

        Conversión de datos reales a simulados:
          - Nombre: tomado directamente de psutil (truncado a 20 chars)
          - burst_time: aleatorio (no conocemos el tiempo real restante)
          - memory_size: proporcional al RSS real del proceso
          - priority: basada en la prioridad real del proceso

        Args:
            max_count: Número máximo de procesos a cargar

        Returns:
            Lista de PCBs creados (aún en estado NEW)
        """
        created: List[PCB] = []

        if PSUTIL_AVAILABLE:
            try:
                procs = []
                for p in psutil.process_iter(['pid', 'name', 'nice', 'memory_info']):
                    try:
                        info = p.info
                        if info['name'] and len(procs) < max_count:
                            procs.append(info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied,
                            psutil.ZombieProcess):
                        continue

                for info in procs:
                    # Convertir uso de memoria real a bloques simulados
                    mem_bytes = 0
                    if info.get('memory_info'):
                        mem_bytes = info['memory_info'].rss
                    mem_mb = mem_bytes // (1024 * 1024)  # bytes → MB

                    # Escalar a bloques (1 a 4 bloques de block_size_mb)
                    block_size = self.memory.block_size_mb
                    mem_blocks = max(1, min(4, (mem_mb // block_size) + 1))

                    # Convertir prioridad del SO a nuestra escala 0-9
                    # En Unix, nice va de -20 (alta) a +19 (baja)
                    # En Windows, similar con valores numéricos
                    raw_nice = info.get('nice') or 0
                    priority = max(0, min(9, 5 + (raw_nice // 4)))

                    pcb = PCB(
                        name=str(info['name'])[:20],
                        is_system=True,
                        burst_time=random_burst_time(15, 50),
                        priority=priority,
                        memory_size=mem_blocks,
                    )
                    pcb.has_error = random.random() < 0.005  # 0.5% de error
                    created.append(pcb)

            except Exception:
                # Si psutil falla por cualquier razón, usar procesos simulados
                created = self._make_simulated_processes(max_count)
        else:
            created = self._make_simulated_processes(max_count)

        # Registrar en el diccionario global
        for pcb in created:
            self.all_processes[pcb.pid] = pcb
            self.new_queue.append(pcb)

        return created

    def create_process(
        self,
        name: Optional[str] = None,
        burst_time: Optional[int] = None,
        priority: Optional[int] = None,
        memory_size: Optional[int] = None,
        current_tick: int = 0,
    ) -> PCB:
        """
        Crea un proceso manualmente.

        Args:
            name        : Nombre (auto-generado si None)
            burst_time  : Ticks de CPU requeridos (aleatorio si None)
            priority    : Prioridad 0-9 (aleatorio si None)
            memory_size : Bloques de memoria (aleatorio si None)
            current_tick: Tick de llegada al sistema

        Returns:
            El PCB creado en estado NEW
        """
        if name is None:
            self._manual_count += 1
            name = f"Proc-{self._manual_count}"

        pcb = PCB(
            name=name,
            is_system=False,
            burst_time=burst_time if burst_time else random_burst_time(),
            priority=priority if priority is not None else random_priority(),
            memory_size=memory_size if memory_size else random_memory_size(),
            arrival_tick=current_tick,
        )
        pcb.has_error = random.random() < 0.005  # 0.5% de probabilidad de error

        self.all_processes[pcb.pid] = pcb
        self.new_queue.append(pcb)
        return pcb

    # ── Transiciones de Estado ────────────────────────────────────────────────

    def admit_processes(self, current_tick: int) -> List[PCB]:
        """
        Transiciona procesos de NEW → READY (si hay memoria disponible).

        Esta es la función del SCHEDULER DE LARGO PLAZO:
        controla cuántos procesos entran simultáneamente al sistema.
        Si no hay memoria, el proceso espera en new_queue.

        Returns:
            Lista de PCBs admitidos (pasaron a READY, listos para el scheduler)
        """
        admitted: List[PCB] = []
        still_waiting: List[PCB] = []

        for pcb in self.new_queue:
            if self.memory.allocate(pcb):
                # ¡Hay memoria! El proceso puede entrar al sistema
                pcb.state = ProcessState.READY
                pcb.arrival_tick = current_tick
                admitted.append(pcb)
            else:
                # Sin memoria: el proceso sigue esperando en new_queue
                still_waiting.append(pcb)

        self.new_queue = still_waiting
        return admitted

    def block_process(self, pcb: PCB, device: str, duration: int) -> None:
        """
        Bloquea un proceso por I/O (RUNNING → WAITING).

        El engine llama esto cuando maneja una interrupción IO_REQUEST.

        Args:
            pcb     : Proceso a bloquear
            device  : Dispositivo que solicita ("KEYBOARD", "DISK", "PRINTER")
            duration: Ticks de espera (el tiempo del dispositivo controla esto)
        """
        pcb.state = ProcessState.WAITING
        pcb.io_device = device
        pcb.io_remaining = duration

        if pcb not in self.waiting_queue:
            self.waiting_queue.append(pcb)

    def update_waiting_processes(self) -> List[PCB]:
        """
        Decrementa io_remaining de procesos en WAITING.
        Los que completan su espera pasan a READY.

        NOTE: Este método maneja la espera basada en io_remaining del PCB.
        El IOManager también tiene su propio contador por dispositivo.
        El engine usa AMBOS para mayor realismo visual.

        Returns:
            Lista de PCBs que completaron su espera y vuelven a READY
        """
        completed: List[PCB] = []
        still_waiting: List[PCB] = []

        for pcb in self.waiting_queue:
            pcb.io_remaining -= 1
            if pcb.io_remaining <= 0:
                # I/O completo: el proceso puede volver a competir por la CPU
                pcb.io_remaining = 0
                pcb.io_device = None
                pcb.state = ProcessState.READY
                completed.append(pcb)
            else:
                still_waiting.append(pcb)

        self.waiting_queue = still_waiting
        return completed

    def terminate_process(
        self,
        pcb: PCB,
        current_tick: int,
        error: bool = False
    ) -> None:
        """
        Finaliza un proceso (RUNNING → TERMINATED).

        Libera la memoria y registra el timestamp de finalización.

        Args:
            pcb        : Proceso a terminar
            current_tick: Tick de finalización (para turnaround_time)
            error      : True si terminó por error (exit_code=-1)
        """
        pcb.state = ProcessState.TERMINATED
        pcb.finish_tick = current_tick
        pcb.exit_code = -1 if error else 0

        # Liberar los bloques de memoria del proceso
        self.memory.release(pcb)

        # Remover de waiting_queue si estaba esperando
        if pcb in self.waiting_queue:
            self.waiting_queue.remove(pcb)

    def update_waiting_times(self, ready_snapshot: List[PCB]) -> None:
        """
        Incrementa waiting_time de los procesos en la cola READY.

        Llamar cada tick con una copia de la cola del scheduler.
        Esto acumula el tiempo que cada proceso esperó sin ejecutar.

        Args:
            ready_snapshot: Lista de procesos actualmente en cola READY
        """
        for pcb in ready_snapshot:
            if pcb.state == ProcessState.READY:
                pcb.waiting_time += 1

    # ── Consultas ─────────────────────────────────────────────────────────────

    def get_all(self) -> List[PCB]:
        """Todos los procesos (histórico completo, incluidos terminados)."""
        return list(self.all_processes.values())

    def get_active(self) -> List[PCB]:
        """Procesos que no están en TERMINATED."""
        return [p for p in self.all_processes.values()
                if p.state != ProcessState.TERMINATED]

    # ── Privado ───────────────────────────────────────────────────────────────

    def _make_simulated_processes(self, count: int) -> List[PCB]:
        """
        Genera procesos simulados cuando psutil no está disponible.
        Usa nombres de procesos típicos del SO para hacer la simulación
        más realista e interesante para los estudiantes.
        """
        processes: List[PCB] = []
        for i in range(count):
            name = self.SIMULATED_NAMES[i % len(self.SIMULATED_NAMES)]
            pcb = PCB(
                name=name,
                is_system=True,
                burst_time=random_burst_time(15, 50),
                priority=random_priority(0, 5),  # El SO tiene prioridad alta
                memory_size=random_memory_size(1, 3),
            )
            pcb.has_error = random.random() < 0.005
            processes.append(pcb)
        return processes

    def reset(self) -> None:
        """
        Reinicia el gestor de procesos para una nueva simulación.
        También reinicia el contador de PIDs.
        """
        reset_pid_counter()
        self.all_processes.clear()
        self.new_queue.clear()
        self.waiting_queue.clear()
        self._manual_count = 0
