"""
utils/randomizer.py — Utilidades para valores aleatorios.

Centraliza la generación de valores aleatorios usados en la simulación.
Tener un módulo dedicado facilita:
  - Testing reproducible (seeds)
  - Modificar rangos desde un solo lugar
  - Documentar el significado de cada valor aleatorio

Según los requerimientos del proyecto:
  - Interrupciones: entre 5 y 20 ticks de intervalo
  - Duración I/O: entre 5 y 20 ticks
  - Errores: 0.5% de probabilidad por proceso por tick
"""

import random
from typing import Optional


def random_burst_time(min_t: int = 10, max_t: int = 50) -> int:
    """Tiempo de ráfaga aleatorio para un nuevo proceso (en ticks)."""
    return random.randint(min_t, max_t)


def random_priority(min_p: int = 0, max_p: int = 9) -> int:
    """Prioridad aleatoria (0 = más alta, 9 = más baja)."""
    return random.randint(min_p, max_p)


def random_memory_size(min_blocks: int = 1, max_blocks: int = 4) -> int:
    """Número de bloques de memoria requeridos por un proceso."""
    return random.randint(min_blocks, max_blocks)


def random_io_duration() -> int:
    """
    Duración de una operación I/O en ticks.
    Según requerimientos: entre 5 y 20 ticks.
    """
    return random.randint(5, 20)


def random_interrupt_interval() -> int:
    """
    Intervalo entre interrupciones aleatorias en ticks.
    Según requerimientos: entre 5 y 20 ticks.
    """
    return random.randint(5, 20)


def should_occur(probability: float) -> bool:
    """
    Determina si un evento ocurre basado en su probabilidad.

    Args:
        probability: Valor entre 0.0 y 1.0

    Returns:
        True si el evento ocurre

    Ejemplos:
        should_occur(0.005) → True con 0.5% de probabilidad (errores fatales)
        should_occur(0.10)  → True con 10% de probabilidad (I/O requests)
    """
    return random.random() < probability


def random_device() -> str:
    """Selecciona un dispositivo I/O aleatorio."""
    return random.choice(["KEYBOARD", "DISK", "PRINTER"])


def random_process_name() -> str:
    """Genera un nombre de proceso simulado."""
    names = [
        "calc.exe", "notepad.exe", "browser.exe", "editor.exe",
        "compiler.exe", "downloader.exe", "updater.exe", "scanner.exe",
        "renderer.exe", "server.exe", "backup.exe", "indexer.exe",
        "monitor.exe", "player.exe", "database.exe", "logger.exe",
    ]
    return random.choice(names)
