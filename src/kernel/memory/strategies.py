"""
kernel/memory/strategies.py — Estrategias de Asignación de Memoria.

Trabajan sobre la lista de MemorySegment del MemoryManager.
La diferencia respecto al bitmap anterior: los huecos son de TAMAÑO VARIABLE.

Comparación de estrategias con un ejemplo:
    Memoria: [OS=64MB][FREE=100MB][P1=20MB][FREE=200MB][P2=30MB][FREE=50MB]
    Proceso que necesita 60MB:

    First Fit → FREE=100MB (primer hueco ≥ 60MB)
                Rápido O(n), fragmenta el inicio

    Best Fit  → FREE=100MB (hueco más pequeño que alcanza: 100 ≥ 60, 200 ≥ 60)
                El 100MB es el menor válido → elegido
                Lento O(n), deja huecos muy pequeños

    Worst Fit → FREE=200MB (hueco más grande)
                Deja sobrante de 140MB (útil para futuros procesos)
                Lento O(n), puede desperdiciar espacio grande
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import MemoryManager


class AllocationStrategy(ABC):
    """Interfaz del patrón Strategy para asignación de memoria."""

    @abstractmethod
    def find(self, segments: list, size_mb: int) -> Optional[int]:
        """
        Encuentra el índice del segmento FREE donde asignar `size_mb` MB.

        Args:
            segments: Lista ordenada de MemorySegment del MemoryManager
            size_mb : Tamaño requerido en MB

        Returns:
            Índice del segmento elegido, o None si no hay espacio suficiente.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


class FirstFitStrategy(AllocationStrategy):
    """
    First Fit — Asigna el PRIMER hueco libre suficientemente grande.

    Complejidad: O(n) en peor caso, O(1) en caso feliz.
    Fragmenta el inicio de la memoria con el tiempo.
    """

    def find(self, segments: list, size_mb: int) -> Optional[int]:
        for i, seg in enumerate(segments):
            if seg.is_free and seg.size >= size_mb:
                return i
        return None

    @property
    def name(self) -> str:
        return "First Fit"


class BestFitStrategy(AllocationStrategy):
    """
    Best Fit — Asigna el hueco libre MÁS PEQUEÑO que sea suficiente.

    Minimiza el desperdicio interno, pero produce fragmentación externa
    al dejar muchos huecos minúsculos.
    Complejidad: O(n) siempre.
    """

    def find(self, segments: list, size_mb: int) -> Optional[int]:
        best_idx = None
        best_size = float("inf")
        for i, seg in enumerate(segments):
            if seg.is_free and seg.size >= size_mb:
                if seg.size < best_size:
                    best_size = seg.size
                    best_idx = i
        return best_idx

    @property
    def name(self) -> str:
        return "Best Fit"


class WorstFitStrategy(AllocationStrategy):
    """
    Worst Fit — Asigna el hueco libre MÁS GRANDE disponible.

    Idea: el sobrante grande puede alojar futuros procesos grandes.
    Útil cuando los procesos futuros son grandes; malo si son pequeños.
    Complejidad: O(n) siempre.
    """

    def find(self, segments: list, size_mb: int) -> Optional[int]:
        worst_idx = None
        worst_size = -1
        for i, seg in enumerate(segments):
            if seg.is_free and seg.size >= size_mb:
                if seg.size > worst_size:
                    worst_size = seg.size
                    worst_idx = i
        return worst_idx

    @property
    def name(self) -> str:
        return "Worst Fit"


def build_strategy(name: str) -> AllocationStrategy:
    """Factory de estrategias por nombre ('first', 'best', 'worst')."""
    strategies = {
        "first": FirstFitStrategy,
        "best":  BestFitStrategy,
        "worst": WorstFitStrategy,
    }
    return strategies.get(name.lower(), FirstFitStrategy)()
