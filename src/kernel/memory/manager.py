"""
kernel/memory/manager.py — Gestor de Memoria Física con Segmentación Lineal.

Reemplaza completamente el sistema de bitmap de bloques fijos.
Implementa segmentación contigua con fragmentación real emergente.

Modelo de memoria (req1.txt — "continua y lineal"):

    start=0MB
    ├─── [OS=64MB]                 ← Kernel, siempre reservado
    ├─── [P1:TEXT=13MB]
    ├─── [P1:DATA=10MB]
    ├─── [P1:HEAP=7MB]
    ├─── [P1:STACK=2MB]
    ├─── [FREE=48MB]               ← Hueco después de que P2 terminó
    ├─── [P3:TEXT=16MB]
    ├─── [P3:DATA=12MB]
    ├─── [P3:HEAP=8MB]
    ├─── [P3:STACK=4MB]
    ├─── [FREE=820MB]              ← Hueco grande al final
    end=1024MB

La fragmentación EMERGE NATURALMENTE:
    - P2 ocupa [77-110MB], luego termina
    - Deja hueco [77-110MB] = 33MB
    - Si P4 necesita 40MB, no cabe ahí → fragmentación externa

Coalescencia:
    Al liberar un segmento, se fusiona con huecos adyacentes.
    Si P1 y P3 terminan, sus 4 segmentos se convierten en 1 FREE grande.

Integración futura con paginación (req usuario):
    - La interfaz AbstractMMU permite cambiar SegmentMMU por PagedMMU
    - MemoryManager seguiría gestionando los segmentos físicos
    - La MMU traduciría las direcciones virtuales a físicas
    - El campo HardwareConfig.virtual_memory_enabled activa el cambio
"""

from __future__ import annotations

from typing import List, Optional, Dict, TYPE_CHECKING
from .mmu import AbstractMMU, SegmentMMU
from .strategies import AllocationStrategy, FirstFitStrategy, build_strategy
from ..models.memory_segment import MemorySegment, SegmentType
from ..models.pcb import PCB

if TYPE_CHECKING:
    pass


# MB reservados para el kernel simulado (base de la memoria)
OS_RESERVED_MB = 64


class MemoryManager:
    """
    Gestor de Memoria Física Simulada.

    Mantiene una lista ordenada de MemorySegment que representa el
    estado completo de la RAM física en un instante dado.

    Responsabilidades:
        - allocate(pcb):  Asignar N segmentos contiguos a un proceso
        - release(pcb):   Liberar los segmentos de un proceso + coalescencia
        - snapshot():     Retornar copia del estado para la UI
        - get_mmu_info(): Retornar datos de traducción de direcciones
        - change_strategy(): Cambiar algoritmo de asignación en caliente
    """

    def __init__(
        self,
        total_mb: int = 1024,
        strategy: AllocationStrategy | None = None,
        mmu: AbstractMMU | None = None,
    ) -> None:
        self.total_mb: int = total_mb
        self.strategy: AllocationStrategy = strategy or FirstFitStrategy()
        self.mmu: AbstractMMU = mmu or SegmentMMU()

        # Lista ordenada de segmentos (invariante: suma sizes == total_mb)
        self.segments: List[MemorySegment] = []
        self._init_memory()

    def _init_memory(self) -> None:
        """
        Inicializa la memoria con:
            [0] Segmento del SO (OS_RESERVED_MB)
            [1] Segmento libre (total_mb - OS_RESERVED_MB)
        """
        self.segments.clear()
        os_size = min(OS_RESERVED_MB, self.total_mb)
        # Segmento reservado del SO
        self.segments.append(MemorySegment(
            start_address=0,
            size=os_size,
            is_free=False,
            process_id=None,
            segment_type=SegmentType.OS,
        ))
        # Espacio libre restante
        free_size = self.total_mb - os_size
        if free_size > 0:
            self.segments.append(MemorySegment(
                start_address=os_size,
                size=free_size,
                is_free=True,
                segment_type=SegmentType.FREE,
            ))

    # ── Asignación ────────────────────────────────────────────────────────────

    def allocate(self, pcb: PCB) -> bool:
        """
        Asigna memoria a un proceso.

        Divide el espacio del proceso en segmentos TEXT/DATA/HEAP/STACK
        contiguos, usando la estrategia actual para encontrar el hueco.

        Returns:
            True si la asignación fue exitosa, False si no hay espacio.
        """
        size_needed = pcb.memory_size

        # Buscar un hueco contiguo suficientemente grande
        idx = self.strategy.find(self.segments, size_needed)
        if idx is None:
            return False   # Sin espacio: proceso queda en NEW

        seg = self.segments[idx]

        # Si el hueco es más grande, dividirlo
        if seg.size > size_needed:
            leftover = seg.split(size_needed)
            self.segments.insert(idx + 1, leftover)

        # Asignar el segmento encontrado → será el bloque base del proceso
        seg.is_free = False
        seg.process_id = pcb.pid
        seg.segment_type = SegmentType.TEXT  # Marcamos el segmento base como TEXT

        # Registrar en la MMU
        self.mmu.register_process(pcb.pid, seg.start_address, size_needed)

        # Guardar la dirección base en el PCB
        pcb.memory_base_address = seg.start_address

        return True

    # ── Liberación ────────────────────────────────────────────────────────────

    def release(self, pcb: PCB) -> None:
        """
        Libera toda la memoria asociada a un proceso.
        Aplica coalescencia: fusiona huecos adyacentes resultantes.
        """
        # Marcar todos los segmentos del proceso como libres
        for seg in self.segments:
            if seg.process_id == pcb.pid:
                seg.is_free = True
                seg.process_id = None
                seg.segment_type = SegmentType.FREE

        # Desregistrar de la MMU
        self.mmu.unregister_process(pcb.pid)
        pcb.memory_base_address = -1

        # Coalescencia: fusionar segmentos libres adyacentes
        self._coalesce()

    def _coalesce(self) -> None:
        """
        Fusiona segmentos FREE adyacentes en uno solo.
        Reduce la fragmentación externa acumulada.

        Ejemplo:
            [FREE=20MB][FREE=48MB] → [FREE=68MB]
        """
        merged = [self.segments[0]]
        for seg in self.segments[1:]:
            prev = merged[-1]
            if prev.is_free and seg.is_free:
                # Fusionar: agrandar el anterior y descartar el actual
                prev.size += seg.size
            else:
                merged.append(seg)
        self.segments = merged

    # ── Consultas y estadísticas ──────────────────────────────────────────────

    def free_mb(self) -> int:
        """Memoria libre total (suma de todos los huecos)."""
        return sum(s.size for s in self.segments if s.is_free)

    def used_mb(self) -> int:
        """Memoria usada por procesos (excluye OS)."""
        return sum(s.size for s in self.segments if not s.is_free and s.segment_type != SegmentType.OS)

    def usage_percent(self) -> float:
        """Porcentaje de uso: usada_por_procesos / (total - OS)."""
        usable = self.total_mb - OS_RESERVED_MB
        if usable <= 0:
            return 100.0
        return (self.used_mb() / usable) * 100.0

    def fragmentation_external(self) -> float:
        """
        Índice de fragmentación externa (0.0 = sin fragmentación, 1.0 = máxima).

        Definición clásica:
            fragmentación = 1 - (mayor_hueco / total_libre)

        Si toda la memoria libre está en un solo hueco: 0.0
        Si está dispersa en muchos huecos pequeños: → 1.0
        """
        free_segs = [s for s in self.segments if s.is_free]
        if not free_segs:
            return 0.0
        total_free = sum(s.size for s in free_segs)
        largest_free = max(s.size for s in free_segs)
        if total_free == 0:
            return 0.0
        return 1.0 - (largest_free / total_free)

    def free_block_count(self) -> int:
        """Número de huecos libres distintos (indicador de fragmentación)."""
        return sum(1 for s in self.segments if s.is_free)

    def largest_free_block(self) -> int:
        """Tamaño del mayor hueco libre disponible (MB)."""
        free_segs = [s.size for s in self.segments if s.is_free]
        return max(free_segs) if free_segs else 0

    # ── Vista para la UI ──────────────────────────────────────────────────────

    def snapshot(self) -> List[MemorySegment]:
        """
        Retorna una copia de la lista de segmentos para la UI.
        La UI no debe modificar esta lista.
        """
        return list(self.segments)

    def get_mmu_table(self) -> Dict[int, Dict[str, int]]:
        """Retorna la tabla de traducción de la MMU para la UI."""
        if isinstance(self.mmu, SegmentMMU):
            return self.mmu.dump_table()
        return {}

    # ── Configuración en caliente ─────────────────────────────────────────────

    def change_strategy(self, name: str) -> None:
        """Cambia el algoritmo de asignación. Efectivo en la próxima allocate()."""
        self.strategy = build_strategy(name)

    def change_total(self, new_total_mb: int) -> None:
        """
        Cambia el tamaño total de la RAM.
        PRECAUCIÓN: reinicia toda la memoria.
        Solo llamar cuando no haya procesos activos.
        """
        self.total_mb = new_total_mb
        self.mmu.clear() if hasattr(self.mmu, "clear") else None
        self._init_memory()

    def reset(self) -> None:
        """Reinicia la memoria a su estado inicial."""
        if hasattr(self.mmu, "clear"):
            self.mmu.clear()
        self._init_memory()
