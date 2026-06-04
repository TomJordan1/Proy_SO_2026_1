"""
core/engine.py — Motor Principal de la Simulación.

El SimulationEngine es el NÚCLEO del simulador. Coordina todos los subsistemas
y contiene la lógica principal del sistema operativo simulado.

Esta clase NO tiene dependencias de Qt (no importa nada de PySide6).
La UI llama a engine.tick() desde el callback del QTimer.

Flujo completo de un tick:
  ┌─────────────────────────────────────────────────────────────┐
  │ 1. Procesar interrupciones pendientes en la cola            │
  │    → IO_REQUEST: bloquear proceso, enviarlo al dispositivo  │
  │    → PROCESS_ERROR: terminar proceso con error              │
  │    → TIMER: log informativo                                 │
  │                                                             │
  │ 2. Avanzar dispositivos I/O                                 │
  │    → Los que completan devuelven el proceso a READY         │
  │                                                             │
  │ 3. Actualizar procesos en WAITING (countdown io_remaining)  │
  │    → Los que completan vuelven a READY + scheduler          │
  │                                                             │
  │ 4. Admitir procesos NEW → READY (si hay memoria)            │
  │                                                             │
  │ 5. Ejecutar proceso en CPU:                                 │
  │    a. Decrementar remaining_time                            │
  │    b. Si terminó → TERMINATED + liberar CPU                 │
  │    c. Si quantum expiró (RR) → READY + requeue              │
  │                                                             │
  │ 6. Si CPU idle: despachar siguiente del scheduler           │
  │                                                             │
  │ 7. Actualizar waiting_times (procesos en READY)             │
  │                                                             │
  │ 8. Generar interrupciones aleatorias                        │
  │                                                             │
  │ 9. Actualizar métricas                                      │
  └─────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from .models import PCB, ProcessState
from .scheduler import BaseScheduler, FCFSScheduler, RoundRobinScheduler
from .dispatcher import Dispatcher
from .process_manager import ProcessManager
from .interrupts import InterruptQueue, RandomInterruptGenerator, InterruptType, Interrupt
from memory.memory_manager import MemoryManager
from memory.allocation import build_strategy
from iodev.io_manager import IOManager
from metrics.metrics import MetricsCollector


class SimulationEngine:
    """
    Motor principal de la simulación del Sistema Operativo.

    Arquitectura de dependencias:
      SimulationEngine
        ├── SimClock (externo, en UI)
        ├── ProcessManager → MemoryManager → Bitmap + AllocationStrategy
        ├── Scheduler (FCFS o RoundRobin)
        ├── Dispatcher
        ├── IOManager → [KeyboardDevice, DiskDevice, PrinterDevice]
        ├── InterruptQueue + RandomInterruptGenerator
        └── MetricsCollector

    Args:
        scheduler_name : "FCFS" o "RR"
        quantum        : Quantum para Round Robin (ignorado en FCFS)
        total_blocks   : Bloques totales de memoria simulada
        block_size_mb  : MB por bloque (potencia de 2)
        alloc_strategy : "first", "best", o "worst"
        system_procs   : Número de procesos del SO a cargar al inicio
    """

    def __init__(
        self,
        scheduler_name: str = "FCFS",
        quantum: int = 4,
        total_blocks: int = 32,
        block_size_mb: int = 32,
        alloc_strategy: str = "first",
        system_procs: int = 10,
    ):
        # Guardar configuración para poder hacer reset
        self._config = {
            "scheduler_name": scheduler_name,
            "quantum": quantum,
            "total_blocks": total_blocks,
            "block_size_mb": block_size_mb,
            "alloc_strategy": alloc_strategy,
            "system_procs": system_procs,
        }

        # Inicializar todos los subsistemas
        self._init_subsystems(
            scheduler_name, quantum,
            total_blocks, block_size_mb,
            alloc_strategy
        )

        # Log del sistema (últimos 500 mensajes)
        self.system_log: List[str] = []

        # Tick actual (sincronizado con SimClock)
        self._current_tick: int = 0

        # Cargar procesos iniciales del sistema
        if system_procs > 0:
            procs = self.process_mgr.load_system_processes(system_procs)
            self.metrics.total_created += len(procs)
            self._log(f"[T=0] 🚀 PatatOS iniciado con {len(procs)} procesos del sistema")

    def _init_subsystems(
        self,
        scheduler_name: str,
        quantum: int,
        total_blocks: int,
        block_size_mb: int,
        alloc_strategy: str,
    ) -> None:
        """Inicializa todos los subsistemas internos."""
        # Memoria
        strategy = build_strategy(alloc_strategy)
        self.memory = MemoryManager(total_blocks, block_size_mb, strategy)

        # Gestión de procesos (depende de memoria)
        self.process_mgr = ProcessManager(self.memory)

        # Scheduler y Dispatcher
        self.scheduler: BaseScheduler = self._build_scheduler(scheduler_name, quantum)
        self.scheduler_name: str = scheduler_name
        self.quantum: int = quantum
        self.dispatcher = Dispatcher()

        # I/O
        self.io_mgr = IOManager()

        # Interrupciones
        self.interrupt_queue = InterruptQueue()
        self.rand_interrupts = RandomInterruptGenerator()

        # Métricas
        self.metrics = MetricsCollector()

        # Proceso actual en CPU (None = CPU idle)
        self._cpu_process: Optional[PCB] = None

    # ─────────────────────────────────────────────────────────────────────────
    # TICK PRINCIPAL — llamado por SimClock en cada intervalo
    # ─────────────────────────────────────────────────────────────────────────

    def tick(self, tick_number: int) -> None:
        """
        Ejecuta un tick completo de la simulación.

        Este método es el corazón del simulador. Se llama desde el QTimer
        (a través de SimClock) y ejecuta todas las fases del SO simulado.

        Args:
            tick_number: Número de tick actual (proveniente de SimClock)
        """
        self._current_tick = tick_number

        # ── Fase 1: Procesar interrupciones ──────────────────────────────────
        self._process_interrupts()

        # ── Fase 2: Avanzar dispositivos I/O ─────────────────────────────────
        io_done = self.io_mgr.tick()
        for pcb in io_done:
            if pcb.state == ProcessState.WAITING:
                # El dispositivo terminó: el proceso puede volver a ejecutar
                pcb.state = ProcessState.READY
                pcb.io_device = None
                pcb.io_remaining = 0
                self.scheduler.add(pcb)
                # Remover de waiting_queue del process_mgr si estaba ahí
                if pcb in self.process_mgr.waiting_queue:
                    self.process_mgr.waiting_queue.remove(pcb)
                self._log(f"[T={tick_number}] {pcb.name} completó I/O → READY")

        # ── Fase 3: Actualizar procesos en WAITING (countdown propio) ─────────
        # Procesos que no están en un dispositivo pero tienen io_remaining > 0
        # (por ejemplo, interrupciones TIMER que pusieron procesos a esperar)
        completed_wait = self.process_mgr.update_waiting_processes()
        for pcb in completed_wait:
            self.scheduler.add(pcb)
            self._log(f"[T={tick_number}] {pcb.name} terminó espera → READY")

        # ── Fase 4: Admitir procesos NEW → READY ──────────────────────────────
        admitted = self.process_mgr.admit_processes(tick_number)
        for pcb in admitted:
            self.scheduler.add(pcb)
            self._log(
                f"[T={tick_number}] 🆕 {pcb.name} (PID={pcb.pid}) admitido → READY"
            )

        # ── Fase 5: Ejecutar proceso en CPU ───────────────────────────────────
        self._run_cpu(tick_number)

        # ── Fase 6: Despachar si CPU idle ─────────────────────────────────────
        self._dispatch_if_idle(tick_number)

        # ── Fase 7: Actualizar waiting_times ──────────────────────────────────
        # Los procesos en READY acumulan tiempo de espera cada tick
        self.process_mgr.update_waiting_times(self.scheduler.snapshot())

        # ── Fase 8: Generar interrupciones aleatorias ─────────────────────────
        new_ints = self.rand_interrupts.check(tick_number, self._cpu_process)
        for intr in new_ints:
            self.interrupt_queue.push(intr)

        # ── Fase 9: Actualizar métricas ───────────────────────────────────────
        cpu_busy = self._cpu_process is not None
        self.metrics.update(tick_number, cpu_busy, self.process_mgr.get_all())

    # ─────────────────────────────────────────────────────────────────────────
    # Fases internas del tick
    # ─────────────────────────────────────────────────────────────────────────

    def _run_cpu(self, tick: int) -> None:
        """
        Ejecuta un tick de la CPU con el proceso actual.

        Maneja:
          - Decremento de remaining_time
          - Terminación normal del proceso
          - Expiración de quantum (Round Robin)
        """
        pcb = self._cpu_process
        if pcb is None or pcb.state != ProcessState.RUNNING:
            return

        # Decrementar tiempo restante en CPU
        pcb.remaining_time -= 1
        pcb.quantum_used += 1

        # Simular el avance del program counter (4-16 bytes por tick)
        # En un SO real: el PC apunta a la siguiente instrucción en memoria
        pcb.program_counter += random.randint(4, 16)

        # ── ¿Terminó el proceso? ──────────────────────────────────────────────
        if pcb.remaining_time <= 0:
            pcb.remaining_time = 0
            error = pcb.has_error  # 0.5% de los procesos tienen has_error=True
            self.process_mgr.terminate_process(pcb, tick, error=error)
            self._cpu_process = None
            self.dispatcher.release_cpu()

            status = "ERROR ❌" if error else "OK ✓"
            self._log(f"[T={tick}] {pcb.name} TERMINADO ({status})")
            return

        # ── ¿Expiró el quantum? (solo Round Robin) ────────────────────────────
        if isinstance(self.scheduler, RoundRobinScheduler):
            if pcb.quantum_used >= self.scheduler.quantum:
                # Preemption: el proceso vuelve al final de la cola
                self._log(
                    f"[T={tick}] ⏱ {pcb.name} quantum={self.scheduler.quantum} expirado → READY"
                )
                # El dispatcher actualiza el estado del proceso
                self.dispatcher.dispatch(pcb, None, tick, preempted=True)
                # Reencolar al final (rotación de Round Robin)
                self.scheduler.requeue(pcb)
                self._cpu_process = None

    def _dispatch_if_idle(self, tick: int) -> None:
        """
        Si la CPU está libre, despacha el siguiente proceso de la cola READY.

        Pregunta al scheduler quién ejecuta a continuación.
        El dispatcher realiza el cambio de contexto.
        """
        if self._cpu_process is not None:
            return  # CPU ya tiene proceso

        next_pcb = self.scheduler.next()
        if next_pcb is None:
            return  # Cola vacía, CPU idle

        # ¡Context switch! El dispatcher actualiza los estados
        self.dispatcher.dispatch(None, next_pcb, tick)
        self._cpu_process = next_pcb
        self._log(f"[T={tick}] ▶ {next_pcb.name} → RUNNING (CPU)")

    def _process_interrupts(self) -> None:
        """
        Procesa todas las interrupciones pendientes en la cola.

        Las interrupciones se procesan ANTES de ejecutar procesos,
        ya que tienen máxima prioridad en el SO.
        """
        while self.interrupt_queue.has_pending():
            intr = self.interrupt_queue.pop()
            self._handle_interrupt(intr)

    def _handle_interrupt(self, intr: Interrupt) -> None:
        """
        Maneja una interrupción específica según su tipo.

        Tipos de manejo:
          TIMER        → solo log informativo
          IO_REQUEST   → bloquear proceso, enviarlo al dispositivo
          IO_COMPLETE  → (manejado por IOManager.tick())
          PROCESS_ERROR → terminar proceso con exit_code=-1
        """
        tick = self._current_tick

        if intr.type == InterruptType.TIMER:
            # Interrupción de timer: solo informativa en FCFS
            # En RR, el quantum se controla directamente en _run_cpu()
            self._log(f"[T={tick}] ⚡ INT TIMER")

        elif intr.type == InterruptType.IO_REQUEST:
            if intr.pid is None:
                return
            pcb = self.process_mgr.all_processes.get(intr.pid)
            if pcb is None or pcb.state != ProcessState.RUNNING:
                return

            device = intr.device or "DISK"
            duration = intr.duration

            # Bloquear el proceso (RUNNING → WAITING)
            self.process_mgr.block_process(pcb, device, duration)

            # Enregistrar en el dispositivo (para visualización y countdown)
            self.io_mgr.enqueue(pcb, device)

            # Liberar la CPU
            if self._cpu_process == pcb:
                self._cpu_process = None
                self.dispatcher.release_cpu()

            self._log(f"[T={tick}] 🔄 {pcb.name} → WAITING ({device}, {duration}t)")

        elif intr.type == InterruptType.PROCESS_ERROR:
            if intr.pid is None:
                return
            pcb = self.process_mgr.all_processes.get(intr.pid)
            if pcb is None or pcb.state != ProcessState.RUNNING:
                return

            # Terminar el proceso con error
            self.process_mgr.terminate_process(pcb, tick, error=True)
            if self._cpu_process == pcb:
                self._cpu_process = None
                self.dispatcher.release_cpu()

            self._log(f"[T={tick}] ❌ {pcb.name} → ERROR FATAL (exit=-1)")

    # ─────────────────────────────────────────────────────────────────────────
    # Control de la simulación
    # ─────────────────────────────────────────────────────────────────────────

    def create_process(
        self,
        name: Optional[str] = None,
        burst_time: Optional[int] = None,
        priority: Optional[int] = None,
        memory_size: Optional[int] = None,
    ) -> PCB:
        """
        Crea un proceso manualmente desde la UI.

        El proceso inicia en estado NEW y es admitido en el siguiente tick.

        Returns:
            El PCB creado
        """
        pcb = self.process_mgr.create_process(
            name=name,
            burst_time=burst_time,
            priority=priority,
            memory_size=memory_size,
            current_tick=self._current_tick,
        )
        self.metrics.total_created += 1
        self._log(
            f"[T={self._current_tick}] 🆕 Proceso '{pcb.name}' creado "
            f"(PID={pcb.pid}, burst={pcb.burst_time}, mem={pcb.memory_size} bloques)"
        )
        return pcb

    def change_scheduler(self, name: str, quantum: int = 4) -> None:
        """
        Cambia el algoritmo de planificación en tiempo real.

        Los procesos ya en la cola READY se migran al nuevo scheduler.
        El proceso en CPU continúa hasta terminar su tick actual.

        Args:
            name   : "FCFS" o "RR"
            quantum: Quantum para Round Robin
        """
        # Migrar cola existente al nuevo scheduler
        old_queue = self.scheduler.snapshot()
        self.scheduler = self._build_scheduler(name, quantum)
        self.scheduler_name = name
        self.quantum = quantum

        for pcb in old_queue:
            self.scheduler.add(pcb)

        self._log(
            f"[T={self._current_tick}] ⚙ Scheduler cambiado: {name}"
            + (f" (Q={quantum})" if name == "RR" else "")
        )

    def change_alloc_strategy(self, name: str) -> None:
        """
        Cambia la estrategia de asignación de memoria.

        Solo afecta las PRÓXIMAS asignaciones.
        Los procesos ya en memoria mantienen sus bloques.

        Args:
            name: "first", "best", o "worst"
        """
        strategy = build_strategy(name)
        self.memory.change_strategy(strategy)
        self._log(f"[T={self._current_tick}] ⚙ Estrategia de memoria: {strategy.name}")

    def reset(self) -> None:
        """
        Reinicia completamente la simulación.

        Preserva la configuración original (scheduler, quantum, memoria, etc.)
        pero borra todos los procesos, logs y métricas.
        """
        cfg = self._config

        # Reiniciar subsistemas
        self._init_subsystems(
            cfg["scheduler_name"],
            cfg["quantum"],
            cfg["total_blocks"],
            cfg["block_size_mb"],
            cfg["alloc_strategy"],
        )

        # Limpiar log y estado
        self.system_log.clear()
        self._current_tick = 0

        # Cargar procesos del sistema nuevamente
        system_procs = cfg["system_procs"]
        if system_procs > 0:
            procs = self.process_mgr.load_system_processes(system_procs)
            self.metrics.total_created += len(procs)
            self._log(f"[T=0] 🔄 Reset — {len(procs)} procesos del sistema recargados")

    # ─────────────────────────────────────────────────────────────────────────
    # Consultas de estado (usadas por la UI)
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def cpu_process(self) -> Optional[PCB]:
        """Proceso actualmente en la CPU (None si idle)."""
        return self._cpu_process

    @property
    def current_tick(self) -> int:
        """Tick actual de la simulación."""
        return self._current_tick

    @property
    def quantum_remaining(self) -> int:
        """Ticks de quantum restantes para el proceso actual (0 si no es RR)."""
        if not isinstance(self.scheduler, RoundRobinScheduler):
            return 0
        if self._cpu_process is None:
            return 0
        return max(0, self.scheduler.quantum - self._cpu_process.quantum_used)

    def get_ready_queue(self) -> List[PCB]:
        """Copia de la cola READY (para visualización)."""
        return self.scheduler.snapshot()

    def get_waiting_queue(self) -> List[PCB]:
        """Lista de procesos en WAITING (para visualización)."""
        return list(self.process_mgr.waiting_queue)

    def get_all_processes(self) -> List[PCB]:
        """Todos los procesos para la tabla PCB."""
        return self.process_mgr.get_all()

    def get_memory_snapshot(self) -> List[Optional[int]]:
        """Estado de la memoria (lista de PIDs por bloque)."""
        return self.memory.snapshot()

    def get_metrics(self) -> Dict[str, Any]:
        """Métricas actuales de la simulación."""
        return self.metrics.summary()

    def get_io_status(self) -> List[Dict]:
        """Estado de los dispositivos I/O."""
        return self.io_mgr.status_snapshot()

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers privados
    # ─────────────────────────────────────────────────────────────────────────

    def _build_scheduler(self, name: str, quantum: int) -> BaseScheduler:
        """Construye el scheduler por nombre."""
        if name == "RR":
            return RoundRobinScheduler(quantum=quantum)
        return FCFSScheduler()

    def _log(self, message: str) -> None:
        """Agrega un mensaje al log del sistema (máx 500 entradas)."""
        self.system_log.append(message)
        if len(self.system_log) > 500:
            self.system_log.pop(0)
