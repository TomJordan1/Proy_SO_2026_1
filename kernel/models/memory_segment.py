"""
kernel/models/memory_segment.py — Segmento de Memoria Lineal.

La memoria se modela como una lista ordenada de segmentos contiguos.
Esto permite:
    - Fragmentación REAL (huecos de tamaño variable)
    - Vista lineal continua (req1: "NO grilla uniforme")
    - Coalescencia de huecos adyacentes al liberar
    - Estadísticas de fragmentación emergentes

Visualización correcta (req1.txt):
    |OS=64MB|──P1:TEXT──|P1:DATA|P1:HEAP|FREE────────|P2:TEXT|FREE|
    0       64          164     194     214          414     514  ...

Contrasta con el modelo INCORRECTO (bitmap de bloques fijos):
    [SO][SO][P1][P1][  ][  ][P2][  ]  ← grilla uniforme, NO realista
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SegmentType(str, Enum):
    """
    Tipos de segmento en la memoria física simulada.

    OS    : Reservado para el kernel del SO (siempre al inicio)
    TEXT  : Código ejecutable de un proceso (read-only en SO real)
    DATA  : Variables inicializadas + BSS de un proceso
    HEAP  : Memoria dinámica (crece hacia arriba en x86)
    STACK : Pila de llamadas (crece hacia abajo en x86)
    FREE  : Espacio libre disponible para nuevos procesos
    """
    OS    = "OS"
    TEXT  = "TEXT"
    DATA  = "DATA"
    HEAP  = "HEAP"
    STACK = "STACK"
    FREE  = "FREE"


@dataclass
class MemorySegment:
    """
    Representa un segmento contiguo de la memoria física.

    La memoria total es una lista ordenada de estos segmentos:
        [seg0: OS=64MB | seg1: P1=32MB | seg2: FREE=128MB | seg3: P2=48MB | ...]

    Cada segmento tiene:
        start_address : Offset desde 0 (en MB)
        size          : Tamaño del segmento (en MB)
        is_free       : True = libre, False = ocupado
        process_id    : PID del dueño (None si libre o OS)
        segment_type  : Tipo de contenido (OS, TEXT, DATA, HEAP, STACK, FREE)

    Nota de diseño para extensibilidad (paginación futura):
        Con memoria virtual, 'start_address' pasaría a ser una dirección
        LÓGICA del proceso, y la MMU realizaría la traducción a físico.
        El MemorySegment seguiría siendo el modelo del espacio de proceso.
    """

    start_address: int
    """Dirección física de inicio del segmento, en MB desde 0."""

    size: int
    """Tamaño del segmento en MB. Siempre > 0."""

    is_free: bool = True
    """True si el segmento está disponible para asignación."""

    process_id: Optional[int] = None
    """PID del proceso propietario. None si libre (is_free=True) o SO."""

    segment_type: SegmentType = SegmentType.FREE
    """Tipo de contenido del segmento."""

    # ── Propiedades ────────────────────────────────────────────────────────────

    @property
    def end_address(self) -> int:
        """Dirección del último byte + 1 (exclusivo) del segmento."""
        return self.start_address + self.size

    @property
    def label(self) -> str:
        """
        Etiqueta corta para mostrar en la vista de memoria.
        Ejemplos: "OS", "FREE", "P3:TEXT", "P7:HEAP"
        """
        if self.segment_type == SegmentType.OS:
            return "OS"
        if self.is_free:
            return "FREE"
        pid_str = f"P{self.process_id}" if self.process_id else "?"
        return f"{pid_str}:{self.segment_type.value}"

    def split(self, size: int) -> MemorySegment:
        """
        Divide este segmento (debe ser FREE) en dos partes.

        La primera parte (de tamaño `size`) queda para el asignador.
        La segunda parte (restante) se retorna como nuevo segmento FREE.

        Precondición: self.is_free y size < self.size

        Args:
            size: Tamaño de la porción a extraer (en MB)

        Returns:
            El nuevo segmento FREE que representa el resto.
        """
        leftover = MemorySegment(
            start_address=self.start_address + size,
            size=self.size - size,
            is_free=True,
            process_id=None,
            segment_type=SegmentType.FREE,
        )
        self.size = size
        return leftover

    def __repr__(self) -> str:
        status = "FREE" if self.is_free else f"PID={self.process_id}"
        return (
            f"<Segment [{self.start_address}-{self.end_address}MB] "
            f"{self.segment_type.value} {status}>"
        )
