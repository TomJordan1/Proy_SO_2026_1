"""
simulation/clock.py — Reloj Global de la Simulación.

SimClock emite una señal tick_fired en cada intervalo configurado.
Velocidades: 2000ms (lento) → 80ms (turbo).

Es independiente de toda la lógica del SO simulado.
El engine y la UI se suscriben a tick_fired para reaccionar.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class SimClock(QObject):
    """Reloj global basado en QTimer. Emite tick_fired(tick: int)."""

    tick_fired = Signal(int)

    # Velocidades predefinidas
    SPEED_SLOW   = 2000   # ms/tick
    SPEED_NORMAL = 800
    SPEED_FAST   = 250
    SPEED_TURBO  = 80

    def __init__(self, speed_ms: int = SPEED_NORMAL, parent=None) -> None:
        super().__init__(parent)
        self._tick: int = 0
        self._speed_ms: int = speed_ms
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)

    def _on_timeout(self) -> None:
        self._tick += 1
        self.tick_fired.emit(self._tick)

    def start(self) -> None:
        self._timer.start(self._speed_ms)

    def pause(self) -> None:
        self._timer.stop()

    def reset(self) -> None:
        self._timer.stop()
        self._tick = 0

    def set_speed(self, speed_ms: int) -> None:
        self._speed_ms = max(50, speed_ms)
        if self._timer.isActive():
            self._timer.setInterval(self._speed_ms)

    @property
    def current_tick(self) -> int:
        return self._tick

    @property
    def is_running(self) -> bool:
        return self._timer.isActive()
