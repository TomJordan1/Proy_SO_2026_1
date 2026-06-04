"""
memory/memory_manager.py — Gestor de Memoria Principal.

El MemoryManager coordina el Bitmap y la AllocationStrategy para gestionar
la memoria física simulada. Es el punto de entrada para todas las operaciones
de memoria del engine.

Arquitectura de la memoria simulada:
  ┌──────────────────────────────────────────────────────────────────────┐
  │                     Memoria Física Simulada                          │
  │  ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐    │
  │  │ SO │ SO │ P1 │ P1 │FREE│FREE│ P2 │FREE│FREE│FREE│FREE│FREE│    │
  │  └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘    │
  │    0    1    2    3    4    5    6    7    8    9   10   11          │
  │  ←── reserved ──→ ←── P1 ──→      ← P2 →  ←────── libre ────────→ │
  └──────────────────────────────────────────────────────────────────────┘

Cada bloque tiene un tamaño fijo (ej: 32 MB). El tamaño es potencia de 2
para alinear con el hardware real.

EXTENSIBILIDAD hacia Memoria Virtual:
  Esta clase está diseñada para soportar una capa adicional de MMU:
  - memory_address en PCB = índice de bloque físico (actual)
  - Para memoria virtual: memory_address sería dirección virtual,
    una tabla de páginas mapearía a bloques físicos
  - Solo se necesitaría agregar un VirtualMemoryLayer sin cambiar esta clase
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from .bitmap import Bitmap
from .allocation import AllocationStrategy, FirstFitStrategy, build_strategy

if TYPE_CHECKING:
    from core.models import PCB


class MemoryManager:
    """
    Gestor de memoria física simulada con bloques fijos.

    Args:
        total_blocks : Número total de bloques de memoria
        block_size_mb: Tamaño de cada bloque en MB (potencia de 2)
        strategy     : Algoritmo de asignación (First/Best/Worst Fit)

    Ejemplo de configuración:
        MemoryManager(total_blocks=32, block_size_mb=32)
        → 32 × 32 MB = 1024 MB total
        → Un proceso de 128 MB necesita 4 bloques

    Sistema operativo reservado:
        Los primeros 2 bloques son del SO (kernel + estructuras del sistema).
        Esto simula que el kernel siempre está en memoria baja (dirección 0).
    """

    SYSTEM_RESERVED_BLOCKS = 2  # Bloques reservados para el SO

    def __init__(
        self,
        total_blocks: int = 32,
        block_size_mb: int = 32,
        strategy: Optional[AllocationStrategy] = None
    ):
        self.total_blocks: int = total_blocks
        self.block_size_mb: int = block_size_mb
        self.total_mb: int = total_blocks * block_size_mb
        self.strategy: AllocationStrategy = strategy or FirstFitStrategy()

        # Inicializar bitmap
        self.bitmap: Bitmap = Bitmap(total_blocks)

        # Reservar bloques del SO (PID=0 representa el kernel)
        reserved = min(self.SYSTEM_RESERVED_BLOCKS, total_blocks)
        self.bitmap.allocate(0, reserved, pid=0)

    # ── Asignación ────────────────────────────────────────────────────────────

    def allocate(self, pcb: PCB) -> bool:
        """
        Asigna bloques de memoria a un proceso.

        Flujo:
          1. Preguntar a la estrategia: ¿dónde caben `pcb.memory_size` bloques?
          2. Si la estrategia encuentra espacio:
             - Marcar bloques como ocupados en el bitmap
             - Guardar la dirección física en pcb.memory_address
             - Retornar True
          3. Si no hay espacio: retornar False
             (el proceso permanecerá en NEW hasta que haya memoria)

        Args:
            pcb: Proceso a quien asignar memoria

        Returns:
            True si se asignó exitosamente, False si no hay espacio
        """
        size = pcb.memory_size

        # Consultar a la estrategia de asignación dónde poner el proceso
        start_index = self.strategy.find_block(self.bitmap, size)

        if start_index is None:
            return False  # Sin espacio suficiente

        # Marcar bloques como ocupados en el bitmap
        self.bitmap.allocate(start_index, size, pcb.pid)

        # Registrar la dirección física en el PCB
        # Dirección = índice_bloque × tamaño_bloque (en MB)
        # En un SO real, esta sería la dirección física en bytes
        pcb.memory_address = start_index * self.block_size_mb

        return True

    def release(self, pcb: PCB) -> None:
        """
        Libera la memoria de un proceso.

        Cuando el proceso termina (TERMINATED), sus bloques vuelven
        a estar disponibles para nuevos procesos.

        Args:
            pcb: Proceso cuya memoria se libera
        """
        if pcb.pid > 0:  # No liberar memoria del SO (pid=0)
            self.bitmap.free(pcb.pid)
            pcb.memory_address = -1

    def change_strategy(self, strategy: AllocationStrategy) -> None:
        """
        Cambia la estrategia de asignación en tiempo de ejecución.

        Los procesos ya asignados mantienen su memoria.
        Solo afecta a las PRÓXIMAS asignaciones.

        Esto permite comparar estrategias durante la simulación.
        """
        self.strategy = strategy

    # ── Consultas ─────────────────────────────────────────────────────────────

    def free_blocks(self) -> int:
        """Bloques libres disponibles (sin contar los del SO)."""
        return self.bitmap.free_count()

    def used_blocks(self) -> int:
        """Bloques ocupados (incluye los del SO)."""
        return self.bitmap.used_count()

    def usage_percent(self) -> float:
        """Porcentaje de memoria en uso (0-100)."""
        if self.total_blocks == 0:
            return 0.0
        return (self.used_blocks() / self.total_blocks) * 100.0

    def fragmentation_external(self) -> float:
        """
        Fragmentación externa: proporción de memoria libre INUTILIZABLE.

        Fórmula: 1 - (mayor_hueco_libre / total_libre)

        Valor 0.0 = sin fragmentación (un solo hueco grande)
        Valor 1.0 = máxima fragmentación (muchos huecos de 1 bloque)

        Esta métrica motiva el uso de memoria virtual en el futuro:
        la paginación elimina la fragmentación externa.
        """
        free = self.bitmap.free_count()
        if free == 0:
            return 0.0

        # Encontrar el hueco más grande
        max_run = 0
        current_run = 0
        for i in range(self.total_blocks):
            if self.bitmap.is_free(i):
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 0

        return 1.0 - (max_run / free)

    # ── Visualización ─────────────────────────────────────────────────────────

    def snapshot(self) -> List[Optional[int]]:
        """
        Estado actual de la memoria como lista de PIDs por bloque.

        Retorna:
            Lista donde cada posición es un bloque:
            - None : libre
            - 0    : reservado para el SO
            - N    : proceso con PID=N

        Ejemplo: [0, 0, 3, 3, None, None, 5, None, ...]

        La UI lee esto para pintar el mapa de memoria visual.
        """
        return self.bitmap.snapshot()

    def reset(self, strategy_name: str = "first") -> None:
        """
        Reinicia la memoria para una nueva simulación.

        Args:
            strategy_name: Estrategia a usar después del reset
        """
        self.bitmap = Bitmap(self.total_blocks)
        reserved = min(self.SYSTEM_RESERVED_BLOCKS, self.total_blocks)
        self.bitmap.allocate(0, reserved, pid=0)
        self.strategy = build_strategy(strategy_name)
