"""
simulation/engine.py — Motor de Simulación Multi-CPU.

El SimulationEngine es el núcleo del simulador.
Puede ejecutarse sin interfaz gráfica (req3.txt).

Flujo de cada tick (8 fases, req1.txt):
    1. INTERRUPTS  — Procesar cola de interrupciones pendientes
    2. IO_TICK     — Avanzar dispositivos I/O, devolver completados a READY
    3. SCHEDULER   — Aplicar aging y reglas propias de cada scheduler
    4. PROCESSES   — Mover NEW→READY, decrementar remaining_time
    5. CPU_EXECUTE — Ejecutar procesos en cada core (execute_tick)
    6. PREEMPTION  — Verificar si schedulers expropiativos deben expulsar
    7. ASSIGN      — Asignar procesos a cores libres (dispatcher)
    8. METRICS     — Actualizar métricas globales

Multi-CPU:
    Cada CPUCore tiene:
        - Su propia instancia de scheduler
        - Un proceso activo (o None si idle)
        - Un contador de ticks en overhead de context switch
    El engine hace load balancing: nuevos procesos al core menos cargado.

Interrupciones emergentes (no aleatorias):
    io_prob y syscall_prob de cada proceso se evalúan determinísticamente
    usando hash(pid, tick, salt), garantizando reproducibilidad.
"""
from __future__ import annotations

import random
import psutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .config import HardwareConfig
from kernel.models.pcb import PCB, ProcessState, ProcessType, _TYPE_PROFILES, reset_pid_counter
from kernel.models.interrupt import (
    Interrupt, InterruptType,
    deterministic_probability, deterministic_duration,
)
from kernel.memory.manager import MemoryManager
from kernel.memory.strategies import build_strategy
from kernel.memory.mmu import SegmentMMU
from kernel.scheduler.base import BaseScheduler
from kernel.scheduler.fcfs import FCFSScheduler
from kernel.scheduler.sjf import SJFScheduler
from kernel.scheduler.srtf import SRTFScheduler
from kernel.scheduler.priority import PriorityScheduler
from kernel.scheduler.round_robin import RoundRobinScheduler
from kernel.scheduler.mlfq import MLFQScheduler
from kernel.dispatcher.dispatcher import Dispatcher
from kernel.io.manager import IOManager
from kernel.interrupts.controller import InterruptController
from kernel.metrics.collector import MetricsCollector


# ── CPU Core ──────────────────────────────────────────────────────────────────

@dataclass
class CPUCore:
    """
    Representa un core de CPU físico en la simulación.

    Cada core tiene su propio scheduler y proceso activo.
    """
    id: int
    scheduler: BaseScheduler
    process: Optional[PCB] = None
    switch_overhead: int = 0   # Ticks restantes de overhead por context switch
    busy_ticks: int = 0
    idle_ticks: int = 0

    @property
    def is_busy(self) -> bool:
        return self.process is not None

    @property
    def is_switching(self) -> bool:
        return self.switch_overhead > 0


def build_scheduler(
    algorithm: str,
    quantum: int = 4,
    preemptive: bool = True,
    aging_enabled: bool = True,
    aging_interval: int = 20,
) -> BaseScheduler:
    """Factory de schedulers por nombre."""
    alg = algorithm.upper().replace(" ", "")
    if alg == "SJF":
        return SJFScheduler()
    if alg == "SRTF":
        return SRTFScheduler()
    if alg in ("PRIORITY", "PRIO"):
        return PriorityScheduler(preemptive, aging_enabled, aging_interval)
    if alg in ("RR", "ROUNDROBIN"):
        return RoundRobinScheduler(quantum)
    if alg == "MLFQ":
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return MLFQScheduler()
    return FCFSScheduler()   # Default: FCFS


# ── Engine ────────────────────────────────────────────────────────────────────

class SimulationEngine:
    """
    Motor principal del simulador PatatOS.

    Diseño:
        - Independiente de PySide6 / UI (req3.txt)
        - Todo el estado de la simulación vive aquí
        - La UI solo LEE el estado; nunca escribe directamente
        - Puede ejecutarse en modo headless: engine.tick() en un loop Python

    Uso típico:
        config = HardwareConfig(num_cpus=2, scheduler_algorithm="RR")
        engine = SimulationEngine(config)
        # ... luego por cada tick del reloj:
        engine.tick()
        snapshot = engine.get_snapshot()
    """

    def __init__(self, config: HardwareConfig) -> None:
        self.config: HardwareConfig = config
        self.current_tick: int = 0
        self.is_running: bool = False

        # ── Log del sistema ───────────────────────────────────────────────────
        self.system_log: List[str] = []

        # ── Procesos ──────────────────────────────────────────────────────────
        self.processes: Dict[int, PCB] = {}

        # ── CPU Cores ─────────────────────────────────────────────────────────
        self.cores: List[CPUCore] = [
            CPUCore(
                id=i,
                scheduler=build_scheduler(
                    config.scheduler_algorithm,
                    quantum=config.quantum_default,
                    preemptive=config.preemptive,
                    aging_enabled=config.aging_enabled,
                    aging_interval=config.aging_interval,
                ),
            )
            for i in range(config.num_cpus)
        ]

        # ── Memoria ───────────────────────────────────────────────────────────
        self.memory = MemoryManager(
            total_mb=config.total_memory_mb,
            strategy=build_strategy(config.alloc_strategy),
            mmu=SegmentMMU(is_identity=True),
        )

        # ── Dispatcher ────────────────────────────────────────────────────────
        self.dispatcher = Dispatcher(config.context_switch_cost)
        self.dispatcher.set_log_callback(self._log)

        # ── I/O ───────────────────────────────────────────────────────────────
        self.io_manager = IOManager(config.device_latencies())

        # ── Interrupciones ────────────────────────────────────────────────────
        self.interrupt_controller = InterruptController()

        # ── Métricas ──────────────────────────────────────────────────────────
        self.metrics = MetricsCollector(num_cpus=config.num_cpus)

        # ── Timeline (últimos 200 eventos) ────────────────────────────────────
        self.timeline: List[Tuple[int, Optional[int], str, str, str]] = []
        """(tick, core_id, pid_str, from_state, to_state)"""

        # ── Cargar procesos iniciales ──────────────────────────────────────────
        self._load_initial_processes()

    # ─────────────────────────────────────────────────────────────────────────
    # Tick principal (8 fases)
    # ─────────────────────────────────────────────────────────────────────────

    def tick(self, tick_number: int = 0) -> None:
        """
        Ejecuta un tick completo de la simulación.

        El parámetro tick_number es ignorado: el engine lleva su propio
        contador interno para garantizar consistencia.
        """
        self.current_tick += 1
        t = self.current_tick

        # ── Fase 1: Interrupciones globales ───────────────────────────────────
        self._phase_interrupts()

        # ── Fase 2: I/O devices tick ──────────────────────────────────────────
        self._phase_io_tick()

        # ── Fase 3: Scheduler hooks (aging, etc.) ─────────────────────────────
        self._phase_scheduler_hooks()

        # ── Fase 4: Mover NEW→READY, actualizar waiting_time ─────────────────
        self._phase_process_update()

        # ── Fase 5: Ejecutar procesos en CPU ──────────────────────────────────
        self._phase_cpu_execute()

        # ── Fase 6: Verificar preemption ──────────────────────────────────────
        self._phase_preemption()

        # ── Fase 7: Asignar cores libres ──────────────────────────────────────
        self._phase_assign()

        # ── Fase 8: Actualizar métricas ───────────────────────────────────────
        active_cores = sum(1 for c in self.cores if c.is_busy)
        self.metrics.record_tick(active_cores)

        # Auto-crear procesos si está habilitado
        if self.config.auto_create and random.random() < 0.20:
            self._auto_create_process()

    # ─────────────────────────────────────────────────────────────────────────
    # Fases del tick
    # ─────────────────────────────────────────────────────────────────────────

    def _phase_interrupts(self) -> None:
        """Procesar interrupciones pendientes en la cola."""
        interrupts = self.interrupt_controller.drain()
        for intr in interrupts:
            self.metrics.record_interrupt(intr.type.value)
            if intr.type == InterruptType.TIMER:
                self._log(f"[T={self.current_tick}] TIMER interrupt")
            elif intr.type == InterruptType.PROCESS_ERROR:
                pcb = self.processes.get(intr.pid)
                if pcb and pcb.state == ProcessState.RUNNING:
                    self._terminate_process(pcb, exit_code=-1)

    def _phase_io_tick(self) -> None:
        """Avanzar dispositivos I/O y devolver los completados a READY."""
        completed = self.io_manager.tick()
        for pcb in completed:
            if pcb.pid in self.processes:
                self._to_ready(pcb, "IO_COMPLETE")

    def _phase_scheduler_hooks(self) -> None:
        """Llamar on_tick() de cada scheduler (aging, boosts, etc.)."""
        for core in self.cores:
            core.scheduler.on_tick(self.current_tick)

    def _phase_process_update(self) -> None:
        """Mover procesos NEW→READY (si tienen memoria) y contar waiting."""
        for pcb in list(self.processes.values()):
            if pcb.state == ProcessState.NEW:
                # Intentar asignar memoria
                ok = self.memory.allocate(pcb)
                if ok:
                    self._to_ready(pcb, "NEW_ADMITTED")
                else:
                    # Sin memoria: contar como rechazado si lleva muchos ticks en NEW
                    pass
            elif pcb.state == ProcessState.READY:
                pcb.waiting_time += 1
            elif pcb.state == ProcessState.WAITING and pcb.io_device == "SYSCALL":
                pcb.io_remaining -= 1
                if pcb.io_remaining <= 0:
                    self._to_ready(pcb, "SYSCALL_COMPLETE")

    def _phase_cpu_execute(self) -> None:
        """Ejecutar un tick de CPU en cada core activo."""
        for core in self.cores:
            if core.switch_overhead > 0:
                core.switch_overhead -= 1
                continue   # Core en overhead de context switch

            pcb = core.process
            if not pcb:
                core.idle_ticks += 1
                continue

            if pcb.state != ProcessState.RUNNING:
                continue

            # Verificar si el proceso va a error
            if pcb.has_error:
                err_prob = deterministic_probability(pcb.pid, self.current_tick, "error")
                progress = 1.0 - (pcb.remaining_time / max(1, pcb.burst_time))
                if progress >= 0.1 and err_prob < self.config.error_probability * 20:
                    self.interrupt_controller.raise_interrupt(Interrupt(
                        type=InterruptType.PROCESS_ERROR,
                        pid=pcb.pid,
                        tick=self.current_tick,
                    ))
                    continue

            # Verificar si el proceso solicita I/O
            if self._check_io_request(pcb):
                core.process = None
                continue

            # Verificar syscall
            if self._check_syscall(pcb):
                core.process = None
                continue

            # Ejecutar instrucciones del proceso
            pcb.execute_tick()
            pcb.remaining_time -= 1
            pcb.quantum_used += 1
            pcb.quantum_remaining = max(0, pcb.quantum_remaining - 1)
            core.busy_ticks += 1

            # ¿Terminó?
            if pcb.remaining_time <= 0:
                core.process = None
                self._terminate_process(pcb, exit_code=0)

    def _phase_preemption(self) -> None:
        """Verificar si schedulers expropiativos deben expulsar el proceso actual."""
        for core in self.cores:
            if not core.process or core.switch_overhead > 0:
                continue
            pcb = core.process
            if pcb.state != ProcessState.RUNNING:
                continue

            if core.scheduler.should_preempt(pcb, self.current_tick):
                # Expulsar el proceso actual
                cost = self.dispatcher.dispatch(pcb, None, core.id, self.current_tick)
                core.switch_overhead = cost
                core.scheduler.add_process(pcb)
                core.process = None
                self.metrics.record_context_switch(cost)
                self._add_timeline(core.id, pcb.pid, pcb.name, "RUNNING", "READY")
                self._log(
                    f"[T={self.current_tick}] PREEMPT P{pcb.pid} ({pcb.name}) "
                    f"← {core.scheduler.name}"
                )

    def _phase_assign(self) -> None:
        """Asignar procesos a cores libres mediante el dispatcher."""
        for core in self.cores:
            if core.process is not None or core.switch_overhead > 0:
                continue

            # Pedir el siguiente proceso al scheduler del core
            next_pcb = core.scheduler.select_next(self.current_tick)
            if not next_pcb:
                continue

            # Context switch
            cost = self.dispatcher.dispatch(None, next_pcb, core.id, self.current_tick)
            core.switch_overhead = cost
            core.process = next_pcb
            self.metrics.record_context_switch(cost)
            self._add_timeline(core.id, next_pcb.pid, next_pcb.name, "READY", "RUNNING")

    # ─────────────────────────────────────────────────────────────────────────
    # Lógica de I/O y syscall
    # ─────────────────────────────────────────────────────────────────────────

    def _check_io_request(self, pcb: PCB) -> bool:
        """
        Determina si el proceso solicita I/O este tick (determinístico).
        Si sí, lo envía al dispositivo y lo pone en WAITING.
        """
        effective_io_prob = self.config.effective_io_probability(pcb.io_probability)
        prob = deterministic_probability(pcb.pid, self.current_tick, "io")
        if prob >= effective_io_prob:
            return False

        # Elegir dispositivo según tipo de proceso
        device = self._select_device_for_process(pcb)

        # Calcular duración según latencia del dispositivo
        lat = self.config.device_latencies().get(device, 15)
        duration = deterministic_duration(pcb.pid, f"io_{device}", lat // 2, lat * 2)

        pcb.state = ProcessState.WAITING
        pcb.io_remaining = duration

        accepted = self.io_manager.request(pcb, device, self.current_tick)
        if accepted:
            self._add_timeline(pcb.cpu_id, pcb.pid, pcb.name, "RUNNING", f"WAITING({device})")
            self._log(
                f"[T={self.current_tick}] IO_REQ P{pcb.pid} ({pcb.name}) → {device} "
                f"por {duration}t"
            )
            self.interrupt_controller.raise_interrupt(Interrupt(
                type=InterruptType.IO_REQUEST,
                pid=pcb.pid,
                device=device,
                duration=duration,
                tick=self.current_tick,
            ))
        else:
            # Dispositivo lleno: el proceso continúa (no bloqueante en este tick)
            pcb.state = ProcessState.RUNNING
            pcb.io_remaining = 0
            return False

        return True

    def _check_syscall(self, pcb: PCB) -> bool:
        """Determina si el proceso hace una syscall este tick."""
        prob = deterministic_probability(pcb.pid, self.current_tick, "syscall")
        if prob >= pcb.syscall_probability:
            return False

        duration = deterministic_duration(pcb.pid, "syscall", 1, 4)
        pcb.state = ProcessState.WAITING
        pcb.io_device = "SYSCALL"
        pcb.io_remaining = duration

        # Las syscalls se resuelven como WAITING con contador directo (sin device)
        self._add_timeline(pcb.cpu_id, pcb.pid, pcb.name, "RUNNING", "WAITING(SYSCALL)")
        self._log(f"[T={self.current_tick}] SYSCALL P{pcb.pid} ({pcb.name}) {duration}t")
        return True

    def _select_device_for_process(self, pcb: PCB) -> str:
        """Elige el dispositivo de I/O según el tipo de proceso."""
        if pcb.process_type == ProcessType.IO_BOUND:
            # Los IO-bound usan más disco
            weights = {"DISK": 50, "KEYBOARD": 15, "NETWORK": 20, "USB": 10, "PRINTER": 5}
        elif pcb.process_type == ProcessType.INTERACTIVE:
            weights = {"KEYBOARD": 40, "DISK": 20, "NETWORK": 25, "USB": 10, "PRINTER": 5}
        elif pcb.process_type == ProcessType.SYSTEM:
            weights = {"DISK": 60, "NETWORK": 20, "USB": 10, "KEYBOARD": 5, "PRINTER": 5}
        else:  # CPU_BOUND
            weights = {"DISK": 40, "PRINTER": 20, "USB": 20, "KEYBOARD": 10, "NETWORK": 10}

        devices = list(weights.keys())
        w = list(weights.values())
        return random.choices(devices, weights=w, k=1)[0]

    # ─────────────────────────────────────────────────────────────────────────
    # Transiciones de estado
    # ─────────────────────────────────────────────────────────────────────────

    def _to_ready(self, pcb: PCB, reason: str) -> None:
        """Pone un proceso en READY y lo agrega al scheduler menos cargado."""
        pcb.state = ProcessState.READY
        pcb.io_device = None
        pcb.io_remaining = 0

        core = self._least_loaded_core()
        core.scheduler.add_process(pcb)

        if reason != "NEW_ADMITTED":
            self._log(f"[T={self.current_tick}] READY P{pcb.pid} ({pcb.name}) ← {reason}")

    def _terminate_process(self, pcb: PCB, exit_code: int = 0) -> None:
        """Finaliza un proceso: libera CPU y memoria, registra métricas."""
        pcb.state = ProcessState.TERMINATED
        pcb.exit_code = exit_code
        pcb.finish_tick = self.current_tick
        pcb.cpu_id = None

        self.memory.release(pcb)
        self.metrics.record_completion(pcb)

        status = f"(exit={exit_code})" if exit_code != 0 else "(OK)"
        self._add_timeline(pcb.cpu_id, pcb.pid, pcb.name, "RUNNING", "TERMINATED")
        self._log(f"[T={self.current_tick}] TERM P{pcb.pid} ({pcb.name}) {status}")

    # ─────────────────────────────────────────────────────────────────────────
    # Creación de procesos
    # ─────────────────────────────────────────────────────────────────────────

    def _load_initial_processes(self) -> None:
        """
        Carga los procesos iniciales según la configuración.
        Si use_system_processes: carga desde psutil.
        Si no: los crea sintéticamente.
        """
        if self.config.use_system_processes:
            self._load_from_psutil(self.config.initial_processes)
        else:
            for _ in range(self.config.initial_processes):
                self._create_synthetic_process()

    def _load_from_psutil(self, count: int) -> None:
        """
        Carga los primeros `count` procesos del SO real usando psutil.
        Los tamaños de memoria son proporcionales al RSS real del proceso.
        """
        try:
            real_procs = [
                p for p in psutil.process_iter(['pid', 'name', 'memory_info', 'nice'])
                if p.info['memory_info'] is not None
            ][:count]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            real_procs = []

        for rp in real_procs:
            try:
                rss_mb = max(1, rp.info['memory_info'].rss // (1024 * 1024))
                # Limitar al máximo configurado
                mem_mb = min(rss_mb, self.config.max_process_mb)
                mem_mb = max(1, mem_mb)

                # Tipo de proceso según nombre (heurística)
                name = rp.info['name'] or "proc"
                ptype = self._guess_process_type(name)

                profile = _TYPE_PROFILES[ptype]
                burst = random.randint(profile["burst_min"], profile["burst_max"])
                priority = random.randint(profile["priority_min"], profile["priority_max"])

                pcb = PCB(
                    name=name[:16],
                    process_type=ptype,
                    memory_size=mem_mb,
                    burst_time=burst,
                    priority=priority,
                    arrival_tick=0,
                    has_error=(random.random() < self.config.error_probability),
                )
                self.processes[pcb.pid] = pcb
                self.metrics.total_created += 1
                self._log(f"[T=0] NEW P{pcb.pid} ({pcb.name}) {mem_mb}MB {ptype.value}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def _guess_process_type(self, name: str) -> ProcessType:
        """Heurística para adivinar el tipo de proceso por su nombre."""
        name_lower = name.lower()
        system_names = {"system", "kernel", "kworker", "kthread", "svchost", "winlogon",
                        "csrss", "lsass", "smss", "wininit", "services", "registry"}
        io_names = {"chrome", "firefox", "edge", "explorer", "photoshop", "vlc",
                    "spotify", "discord", "teams", "steam", "word", "excel"}
        interactive_names = {"cmd", "powershell", "bash", "terminal", "code",
                             "notepad", "python", "java"}

        if any(s in name_lower for s in system_names):
            return ProcessType.SYSTEM
        if any(s in name_lower for s in io_names):
            return ProcessType.IO_BOUND
        if any(s in name_lower for s in interactive_names):
            return ProcessType.INTERACTIVE
        return ProcessType.CPU_BOUND

    def _create_synthetic_process(self, ptype: Optional[ProcessType] = None) -> PCB:
        """Crea un proceso sintético con parámetros aleatorios."""
        if ptype is None:
            r = random.random()
            if r < self.config.cpu_bound_ratio:
                ptype = ProcessType.CPU_BOUND
            elif r < self.config.cpu_bound_ratio + 0.35:
                ptype = ProcessType.IO_BOUND
            elif r < self.config.cpu_bound_ratio + 0.55:
                ptype = ProcessType.INTERACTIVE
            else:
                ptype = ProcessType.SYSTEM

        profile = _TYPE_PROFILES[ptype]
        pcb = PCB(
            name=f"P{len(self.processes) + 1}",
            process_type=ptype,
            memory_size=random.randint(profile["mem_min_mb"], min(profile["mem_max_mb"], self.config.max_process_mb)),
            burst_time=random.randint(profile["burst_min"], profile["burst_max"]),
            priority=random.randint(profile["priority_min"], profile["priority_max"]),
            arrival_tick=self.current_tick,
            has_error=(random.random() < self.config.error_probability),
        )
        self.processes[pcb.pid] = pcb
        self.metrics.total_created += 1
        return pcb

    def _auto_create_process(self) -> None:
        """Crea un proceso automáticamente durante la simulación."""
        self._create_synthetic_process()

    def create_process(
        self,
        name: Optional[str] = None,
        burst_time: int = 20,
        priority: int = 5,
        memory_size: int = 32,
        process_type: str = "CPU_BOUND",
    ) -> PCB:
        """
        API pública: crea un proceso manual desde la UI.
        """
        try:
            ptype = ProcessType(process_type)
        except ValueError:
            ptype = ProcessType.CPU_BOUND

        pcb = PCB(
            name=name or f"P{len(self.processes) + 1}",
            process_type=ptype,
            memory_size=memory_size,
            burst_time=burst_time,
            priority=priority,
            arrival_tick=self.current_tick,
        )
        self.processes[pcb.pid] = pcb
        self.metrics.total_created += 1
        self._log(f"[T={self.current_tick}] MANUAL P{pcb.pid} ({pcb.name}) {memory_size}MB")
        return pcb

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _least_loaded_core(self) -> CPUCore:
        """Retorna el core con menor carga en su scheduler."""
        return min(self.cores, key=lambda c: c.scheduler.queue_length())

    def _log(self, msg: str) -> None:
        self.system_log.append(msg)
        if len(self.system_log) > 500:
            self.system_log.pop(0)

    def _add_timeline(self, core_id: Optional[int], pid: int, name: str, from_s: str, to_s: str) -> None:
        self.timeline.append((self.current_tick, core_id, f"P{pid}({name})", from_s, to_s))
        if len(self.timeline) > 200:
            self.timeline.pop(0)

    # ─────────────────────────────────────────────────────────────────────────
    # Snapshots para la UI
    # ─────────────────────────────────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        """
        Retorna el estado completo de la simulación para la UI.
        La UI llama a esto después de cada tick.
        """
        return {
            "tick":           self.current_tick,
            "cores":          self._cores_snapshot(),
            "memory":         self.memory.snapshot(),
            "memory_stats":   self._memory_stats(),
            "mmu_table":      self.memory.get_mmu_table(),
            "ready_queues":   self._ready_queues_snapshot(),
            "waiting":        self._waiting_snapshot(),
            "all_processes":  list(self.processes.values()),
            "io_devices":     self.io_manager.get_all_status(),
            "metrics":        self.metrics.get_snapshot(),
            "timeline":       list(self.timeline[-50:]),
            "log":            list(self.system_log),
        }

    def _cores_snapshot(self) -> List[dict]:
        result = []
        for core in self.cores:
            p = core.process
            result.append({
                "id":          core.id,
                "is_busy":     core.is_busy,
                "is_switching": core.is_switching,
                "switch_overhead": core.switch_overhead,
                "scheduler":   core.scheduler.name,
                "busy_ticks":  core.busy_ticks,
                "process": {
                    "pid":          p.pid,
                    "name":         p.name,
                    "type":         p.type_label,
                    "priority":     p.priority,
                    "burst_time":   p.burst_time,
                    "remaining":    p.remaining_time,
                    "quantum_used": p.quantum_used,
                    "quantum_rem":  p.quantum_remaining,
                    "pc":           p.program_counter,
                    "registers":    dict(p.registers),
                    "completion":   p.completion_percent,
                } if p else None,
            })
        return result

    def _memory_stats(self) -> dict:
        return {
            "total_mb":       self.memory.total_mb,
            "used_mb":        self.memory.used_mb(),
            "free_mb":        self.memory.free_mb(),
            "usage_pct":      round(self.memory.usage_percent(), 1),
            "fragmentation":  round(self.memory.fragmentation_external() * 100, 1),
            "free_blocks":    self.memory.free_block_count(),
            "largest_free":   self.memory.largest_free_block(),
            "strategy":       self.memory.strategy.name,
            "mmu_enabled":    self.config.mmu_enabled,
        }

    def _ready_queues_snapshot(self) -> List[List[dict]]:
        """Una lista de colas por cada core."""
        result = []
        for core in self.cores:
            queue = []
            for pcb in core.scheduler.ready_queue:
                queue.append({
                    "pid":      pcb.pid,
                    "name":     pcb.name,
                    "type":     pcb.type_label,
                    "priority": pcb.priority,
                    "waiting":  pcb.waiting_time,
                    "remaining": pcb.remaining_time,
                })
            result.append(queue)
        return result

    def _waiting_snapshot(self) -> List[dict]:
        """Procesos actualmente en WAITING (I/O o SYSCALL)."""
        waiting = []
        for pcb in self.processes.values():
            if pcb.state == ProcessState.WAITING:
                waiting.append({
                    "pid":      pcb.pid,
                    "name":     pcb.name,
                    "device":   pcb.io_device or "?",
                    "remaining": pcb.io_remaining,
                })
        return waiting

    # ─────────────────────────────────────────────────────────────────────────
    # Configuración en caliente
    # ─────────────────────────────────────────────────────────────────────────

    def change_scheduler(self, core_id: int, algorithm: str) -> None:
        """Cambia el algoritmo del core `core_id` en caliente."""
        if 0 <= core_id < len(self.cores):
            old_queue = self.cores[core_id].scheduler.ready_queue[:]
            new_sched = build_scheduler(
                algorithm,
                quantum=self.config.quantum_default,
                preemptive=self.config.preemptive,
                aging_enabled=self.config.aging_enabled,
                aging_interval=self.config.aging_interval,
            )
            # Migrar procesos pendientes
            for pcb in old_queue:
                new_sched.add_process(pcb)
            self.cores[core_id].scheduler = new_sched
            self._log(f"[T={self.current_tick}] CPU{core_id}: scheduler → {algorithm}")

    def change_alloc_strategy(self, name: str) -> None:
        """Cambia la estrategia de asignación de memoria."""
        self.memory.change_strategy(name)
        self.config.alloc_strategy = name
        self._log(f"[T={self.current_tick}] MEM: estrategia → {name}")

    def change_quantum(self, core_id: int, quantum: int) -> None:
        """Cambia el quantum del scheduler del core."""
        if 0 <= core_id < len(self.cores):
            sched = self.cores[core_id].scheduler
            if hasattr(sched, "quantum"):
                sched.quantum = max(1, quantum)

    def reset(self) -> None:
        """Reinicia toda la simulación al estado inicial."""
        reset_pid_counter()
        self.current_tick = 0
        self.processes.clear()
        self.system_log.clear()
        self.timeline.clear()

        for core in self.cores:
            core.process = None
            core.switch_overhead = 0
            core.busy_ticks = 0
            core.idle_ticks = 0
            core.scheduler.ready_queue.clear()

        self.memory.reset()
        self.dispatcher.reset()
        self.io_manager.reset()
        self.interrupt_controller.reset()
        self.metrics.reset()

        self._load_initial_processes()
        self._log(f"[T=0] RESET — Simulación reiniciada")
