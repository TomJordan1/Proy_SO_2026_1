"""
kernel/memory/mmu.py — Unidad de Manejo de Memoria (MMU).

La MMU es la capa de traducción entre direcciones LÓGICAS (del proceso)
y direcciones FÍSICAS (de la RAM simulada).

Arquitectura extensible (req2.txt + respuesta usuario):
    ┌─────────────────────────────────────────────────────────────┐
    │                     AbstractMMU                             │
    │  translate(pid, logical_addr) → physical_addr               │
    │  get_logical_address(pid)     → logical base del proceso    │
    └──────────────────┬──────────────────────────────────────────┘
                       │
           ┌───────────┴────────────────────────┐
           │                                    │
    SegmentMMU (ACTUAL)              PagedMMU (FUTURO)
    Identidad: lógico = físico       Tabla de páginas
    Un segmento contiguo por proceso Frames no contiguos
    Fácil de visualizar              Más realista
                                     TLB, page faults

Estado actual: SegmentMMU
    - logical_addr == physical_addr (identidad)
    - Muestra la abstracción en la UI: "0x0000 → 0x0040"
    - Prepara la interfaz para que PagedMMU sea un drop-in replacement

Cuando se integre PagedMMU:
    1. Crear kernel/memory/paged_mmu.py que implemente AbstractMMU
    2. En HardwareConfig: virtual_memory_enabled = True
    3. En MemoryManager: self.mmu = PagedMMU(...) en lugar de SegmentMMU(...)
    4. El engine y la UI no cambian (trabajan con AbstractMMU)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Optional


class AbstractMMU(ABC):
    """
    Interfaz base de la Unidad de Manejo de Memoria.

    Cualquier implementación (segmentación, paginación, TLB) debe
    cumplir este contrato. El MemoryManager y el engine solo usan
    esta interfaz, garantizando que el cambio de modo sea transparente.
    """

    @abstractmethod
    def register_process(self, pid: int, base_physical_mb: int, size_mb: int) -> None:
        """
        Registra un proceso y su asignación de memoria.

        Args:
            pid              : PID del proceso
            base_physical_mb : Dirección física base (MB) asignada
            size_mb          : Tamaño total asignado (MB)
        """
        pass

    @abstractmethod
    def unregister_process(self, pid: int) -> None:
        """Elimina el mapeo de un proceso (al terminar)."""
        pass

    @abstractmethod
    def translate(self, pid: int, logical_offset_mb: int) -> Optional[int]:
        """
        Traduce una dirección lógica a física.

        Args:
            pid              : PID del proceso
            logical_offset_mb: Offset lógico desde la base del proceso (MB)

        Returns:
            Dirección física (MB) o None si la dirección es inválida.
        """
        pass

    @abstractmethod
    def get_info(self, pid: int) -> Dict[str, int]:
        """
        Retorna información de traducción para mostrar en la UI.

        Returns:
            Dict con al menos: {"logical_base": int, "physical_base": int, "size": int}
        """
        pass


# ── Registro de proceso en la MMU ─────────────────────────────────────────────

@dataclass
class _SegmentEntry:
    """Entrada de la tabla de segmentos de la SegmentMMU."""
    physical_base_mb: int   # Dirección física donde inicia el proceso
    size_mb: int            # Tamaño del segmento


class SegmentMMU(AbstractMMU):
    """
    MMU de segmentación contigua — implementación ACTUAL.

    Modelo: cada proceso tiene UN segmento contiguo en memoria física.
    La dirección lógica es un OFFSET desde la base del segmento.

    Traducción:
        physical = segment.physical_base + logical_offset

    Con is_identity=True (modo simplificado):
        logical_base == physical_base  (el proceso "ve" sus direcciones físicas)
        Esto simplifica la visualización inicial.

    Cuando se integre PagedMMU, esta clase queda como alternativa
    (segmentación vs paginación) seleccionable desde la config.
    """

    def __init__(self, is_identity: bool = True):
        """
        Args:
            is_identity: Si True, direcciones lógicas == físicas.
                         Si False, las direcciones lógicas inician en 0.
        """
        self.is_identity = is_identity
        self._table: Dict[int, _SegmentEntry] = {}
        """Tabla de segmentos: PID → SegmentEntry"""

    def register_process(self, pid: int, base_physical_mb: int, size_mb: int) -> None:
        self._table[pid] = _SegmentEntry(
            physical_base_mb=base_physical_mb,
            size_mb=size_mb,
        )

    def unregister_process(self, pid: int) -> None:
        self._table.pop(pid, None)

    def translate(self, pid: int, logical_offset_mb: int) -> Optional[int]:
        """
        Traduce dirección lógica a física.

        Modo identidad: physical = physical_base + logical_offset
        (ya que logical_base = physical_base en modo identidad)
        """
        entry = self._table.get(pid)
        if entry is None:
            return None
        if logical_offset_mb < 0 or logical_offset_mb >= entry.size_mb:
            return None   # Segmentation fault simulado
        return entry.physical_base_mb + logical_offset_mb

    def get_info(self, pid: int) -> Dict[str, int]:
        entry = self._table.get(pid)
        if entry is None:
            return {"logical_base": -1, "physical_base": -1, "size": 0}
        logical_base = entry.physical_base_mb if self.is_identity else 0
        return {
            "logical_base":  logical_base,
            "physical_base": entry.physical_base_mb,
            "size":          entry.size_mb,
        }

    def dump_table(self) -> Dict[int, Dict[str, int]]:
        """Retorna toda la tabla para la UI (panel de MMU)."""
        return {pid: self.get_info(pid) for pid in self._table}

    def clear(self) -> None:
        """Limpia la tabla completa (para reset)."""
        self._table.clear()
