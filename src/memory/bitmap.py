"""
memory/bitmap.py — Mapa de Bits para gestión de memoria.

El Bitmap (mapa de bits) rastrea el estado de cada bloque de memoria:
  - False (0) = bloque LIBRE
  - True  (1) = bloque OCUPADO

Es la estructura más eficiente para administrar disponibilidad de bloques:
  - Espacio: N bloques → N bits (1/8 del espacio de un array de enteros)
  - Tiempo: Buscar bloques libres = recorrer el array O(n)

Visualización de un bitmap con 8 bloques:
  ┌────┬────┬──────┬──────┬────┬──────┬──────┬──────┐
  │ SO │ SO │FREE  │FREE  │ P1 │ P1   │FREE  │ P2   │
  │ 0  │ 0  │  0   │  0   │ 1  │ 1    │  0   │ 1    │
  └────┴────┴──────┴──────┴────┴──────┴──────┴──────┘
  Idx:  0    1      2      3    4      5      6      7

El bitmap se combina con las estrategias de asignación (First/Best/Worst Fit)
para decidir DÓNDE colocar un proceso en la memoria física simulada.

EXTENSIBILIDAD hacia Memoria Virtual:
  - Para memoria virtual, este bitmap representa los FRAMES FÍSICOS
  - La capa MMU (Memory Management Unit) agregaría la tabla de páginas
  - El bitmap seguiría funcionando igual, solo cambiaría la capa de traducción
"""

from __future__ import annotations

from typing import List, Optional


class Bitmap:
    """
    Mapa de bits para rastrear bloques de memoria libres/ocupados.

    Args:
        num_blocks: Número total de bloques de memoria simulada
    """

    def __init__(self, num_blocks: int):
        self.num_blocks: int = num_blocks

        # Array de booleanos: índice = bloque, valor = True si OCUPADO
        self._bits: List[bool] = [False] * num_blocks

        # Mapa inverso: índice = bloque, valor = PID del dueño (o None)
        # Permite liberar TODOS los bloques de un proceso en O(n)
        self._owner: List[Optional[int]] = [None] * num_blocks

    # ── Asignación y liberación ───────────────────────────────────────────────

    def allocate(self, start: int, length: int, pid: int) -> None:
        """
        Marca `length` bloques como OCUPADOS por el proceso `pid`,
        comenzando desde el índice `start`.

        Args:
            start : Índice del primer bloque a ocupar
            length: Número de bloques consecutivos
            pid   : PID del proceso propietario
        """
        for i in range(start, start + length):
            if 0 <= i < self.num_blocks:
                self._bits[i] = True
                self._owner[i] = pid

    def free(self, pid: int) -> None:
        """
        Libera TODOS los bloques pertenecientes al proceso `pid`.

        Cuando un proceso termina, se llama este método para devolver
        su memoria al sistema. Todos los bloques vuelven a False.

        Complejidad: O(n) — recorre todos los bloques.
        Alternativa más eficiente: mantener mapa PID→[bloques] (tradeoff espacio/tiempo)
        """
        for i in range(self.num_blocks):
            if self._owner[i] == pid:
                self._bits[i] = False
                self._owner[i] = None

    # ── Consultas ─────────────────────────────────────────────────────────────

    def is_free(self, index: int) -> bool:
        """Retorna True si el bloque en `index` está libre."""
        return not self._bits[index]

    def get_owner(self, index: int) -> Optional[int]:
        """Retorna el PID del proceso que ocupa el bloque (None si libre)."""
        return self._owner[index]

    def free_count(self) -> int:
        """Número total de bloques libres."""
        return sum(1 for b in self._bits if not b)

    def used_count(self) -> int:
        """Número total de bloques ocupados."""
        return sum(1 for b in self._bits if b)

    # ── Visualización ─────────────────────────────────────────────────────────

    def snapshot(self) -> List[Optional[int]]:
        """
        Retorna el estado completo del bitmap como lista de PIDs.

        Cada posición corresponde a un bloque:
          - None : bloque libre
          - 0    : reservado por el SO (kernel)
          - N    : bloque del proceso con PID=N

        La UI lee este snapshot para pintar el mapa de memoria visual.

        Ejemplo de retorno:
          [0, 0, None, None, 3, 3, None, 5]
          Significa: bloques 0-1 del SO, 2-3 libres, 4-5 del P3, 6 libre, 7 del P5
        """
        return list(self._owner)
