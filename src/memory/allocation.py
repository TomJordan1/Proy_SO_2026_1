"""
memory/allocation.py — Estrategias de Asignación de Memoria.

Cuando un proceso necesita N bloques, ¿cuál hueco libre elegimos?
Hay tres estrategias clásicas, cada una con sus ventajas y desventajas:

┌─────────────┬────────────────────────────────┬──────────────────────────────┐
│ Estrategia  │ Criterio de selección          │ Consecuencia                 │
├─────────────┼────────────────────────────────┼──────────────────────────────┤
│ First Fit   │ PRIMER hueco suficientemente   │ Rápido pero fragmenta el     │
│             │ grande (izq. a der.)           │ inicio de la memoria         │
├─────────────┼────────────────────────────────┼──────────────────────────────┤
│ Best Fit    │ MENOR hueco que alcance        │ Aprovecha mejor el espacio   │
│             │                                │ pero crea huecos muy pequeños│
├─────────────┼────────────────────────────────┼──────────────────────────────┤
│ Worst Fit   │ MAYOR hueco disponible         │ Deja huecos grandes para     │
│             │                                │ futuros procesos grandes     │
└─────────────┴────────────────────────────────┴──────────────────────────────┘

Ejemplo visual con N=2 bloques (necesitamos 2 bloques contiguos):

  Estado de memoria: [SO][SO][  ][  ][P1][  ][  ][  ][P2][  ]
                       0   1   2   3   4   5   6   7   8   9

  Huecos libres: (2,2) → tamaño 2 en posición 2
                 (5,3) → tamaño 3 en posición 5
                 (9,1) → tamaño 1 en posición 9

  First Fit: elige (2,2) → primer hueco de tamaño >= 2
  Best Fit:  elige (2,2) → hueco más pequeño que alcanza (2 == 2)
  Worst Fit: elige (5,3) → hueco más grande disponible

Patrón STRATEGY:
  - AllocationStrategy define la interfaz
  - FirstFitStrategy, BestFitStrategy, WorstFitStrategy implementan la lógica
  - MemoryManager usa la interfaz → puede cambiar estrategia sin modificar el manager

EXTENSIBILIDAD hacia Memoria Virtual:
  - Estas estrategias trabajan sobre bloques contiguos físicos
  - Para paginación: la búsqueda sería en frames individuales (no contiguos)
  - Se podría agregar PagingAllocationStrategy sin cambiar la interfaz
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .bitmap import Bitmap


# ─────────────────────────────────────────────────────────────────────────────
# Interfaz base (Strategy Pattern)
# ─────────────────────────────────────────────────────────────────────────────

class AllocationStrategy(ABC):
    """
    Interfaz base para estrategias de asignación de memoria.

    Todas las estrategias reciben el bitmap y el tamaño requerido,
    y retornan el índice de inicio del bloque seleccionado (o None).
    """

    @abstractmethod
    def find_block(self, bitmap: Bitmap, size: int) -> Optional[int]:
        """
        Encuentra un bloque contiguo libre de tamaño `size`.

        Args:
            bitmap: Estado actual del bitmap de memoria
            size  : Número de bloques contiguos requeridos

        Returns:
            Índice del primer bloque del hueco seleccionado,
            o None si no hay espacio suficiente.
        """
        pass

    def _find_free_runs(self, bitmap: Bitmap) -> List[Tuple[int, int]]:
        """
        Encuentra todos los segmentos CONTIGUOS de bloques libres.

        Returns:
            Lista de (start_index, length) para cada hueco libre.

        Ejemplo con bitmap [F,F,O,F,F,F,O,F] (F=libre, O=ocupado):
          → [(0, 2), (3, 3), (7, 1)]
        """
        runs: List[Tuple[int, int]] = []
        n = bitmap.num_blocks
        i = 0
        while i < n:
            if bitmap.is_free(i):
                start = i
                # Avanzar mientras los bloques sean libres
                while i < n and bitmap.is_free(i):
                    i += 1
                length = i - start
                runs.append((start, length))
            else:
                i += 1
        return runs

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre de la estrategia para mostrar en UI."""
        pass


# ─────────────────────────────────────────────────────────────────────────────
# First Fit
# ─────────────────────────────────────────────────────────────────────────────

class FirstFitStrategy(AllocationStrategy):
    """
    First Fit — Elige el PRIMER hueco suficientemente grande.

    Algoritmo:
      1. Recorre el bitmap de izquierda a derecha
      2. Al encontrar el PRIMER hueco libre de tamaño >= N, lo retorna
      3. Para inmediatamente (no sigue buscando)

    Ventajas:
      + Más rápido que Best y Worst Fit (no recorre todo el bitmap)
      + Simple de implementar

    Desventajas:
      - Tiende a fragmentar el inicio de la memoria (muchos huecos pequeños)
      - Con el tiempo, el inicio de la memoria queda muy fragmentado

    Complejidad: O(n) en peor caso (no encuentra nada hasta el final)
    """

    def find_block(self, bitmap: Bitmap, size: int) -> Optional[int]:
        for start, length in self._find_free_runs(bitmap):
            if length >= size:
                return start  # ¡Primer hueco que alcanza!
        return None  # Sin espacio suficiente

    @property
    def name(self) -> str:
        return "First Fit"


# ─────────────────────────────────────────────────────────────────────────────
# Best Fit
# ─────────────────────────────────────────────────────────────────────────────

class BestFitStrategy(AllocationStrategy):
    """
    Best Fit — Elige el hueco libre MÁS PEQUEÑO que alcance.

    Algoritmo:
      1. Recorre TODOS los huecos libres del bitmap
      2. Filtra los que tienen tamaño >= N
      3. Elige el de MENOR tamaño entre los válidos

    Ventajas:
      + Minimiza el desperdicio por bloque (overhead interno)
      + Aprovecha mejor el espacio disponible

    Desventajas:
      - Más lento (debe recorrer todo el bitmap)
      - Crea muchos huecos pequeños inutilizables (fragmentación externa)
      - Paradoja: al intentar usar bien el espacio, lo fragmenta más

    Complejidad: O(n) — siempre recorre todo el bitmap
    """

    def find_block(self, bitmap: Bitmap, size: int) -> Optional[int]:
        runs = self._find_free_runs(bitmap)

        # Filtrar huecos suficientemente grandes
        valid = [(start, length) for start, length in runs if length >= size]

        if not valid:
            return None

        # Elegir el de MENOR tamaño (mejor ajuste)
        best_start, _ = min(valid, key=lambda x: x[1])
        return best_start

    @property
    def name(self) -> str:
        return "Best Fit"


# ─────────────────────────────────────────────────────────────────────────────
# Worst Fit
# ─────────────────────────────────────────────────────────────────────────────

class WorstFitStrategy(AllocationStrategy):
    """
    Worst Fit — Elige el hueco libre MÁS GRANDE disponible.

    Algoritmo:
      1. Recorre TODOS los huecos libres del bitmap
      2. Filtra los que tienen tamaño >= N
      3. Elige el de MAYOR tamaño

    Ventajas:
      + Deja huecos grandes para futuros procesos grandes
      + Reduce el número de huecos inutilizables (comparado con Best Fit)

    Desventajas:
      - Puede desperdiciar bloques grandes con procesos pequeños
      - Más lento que First Fit

    Cuándo es mejor que Best Fit:
      Si los procesos futuros son grandes, Worst Fit reserva espacio para ellos.
      Si son pequeños, First Fit o Best Fit son mejores.

    Complejidad: O(n) — siempre recorre todo el bitmap
    """

    def find_block(self, bitmap: Bitmap, size: int) -> Optional[int]:
        runs = self._find_free_runs(bitmap)

        # Filtrar huecos suficientemente grandes
        valid = [(start, length) for start, length in runs if length >= size]

        if not valid:
            return None

        # Elegir el de MAYOR tamaño (peor ajuste = mayor hueco)
        best_start, _ = max(valid, key=lambda x: x[1])
        return best_start

    @property
    def name(self) -> str:
        return "Worst Fit"


# ─────────────────────────────────────────────────────────────────────────────
# Factory helper
# ─────────────────────────────────────────────────────────────────────────────

def build_strategy(name: str) -> AllocationStrategy:
    """
    Construye una estrategia de asignación por nombre.

    Args:
        name: "first", "best", o "worst"

    Returns:
        Instancia de la estrategia correspondiente
    """
    strategies = {
        "first": FirstFitStrategy,
        "best":  BestFitStrategy,
        "worst": WorstFitStrategy,
    }
    cls = strategies.get(name.lower(), FirstFitStrategy)
    return cls()
