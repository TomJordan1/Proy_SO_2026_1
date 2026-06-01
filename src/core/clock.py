"""
core/clock.py — Reloj central de la simulación.

El reloj controla el avance de los "ticks" de simulación.
Cada tick representa una unidad de tiempo del sistema operativo simulado.

Por qué QTimer (no threading.Thread):
  - QTimer es seguro para UI: el callback ocurre en el hilo principal de Qt
  - Evita condiciones de carrera con los widgets de Qt
  - threading.Thread requeriría locks y emit() thread-safe (más complejo)
  - Para una simulación educativa, 1 tick por vez es suficiente y más claro

Velocidades predefinidas:
  ┌──────────┬────────────┬─────────────────────────────┐
  │ Nombre   │ ms/tick    │ Descripción                 │
  ├──────────┼────────────┼─────────────────────────────┤
  │ SLOW     │ 2000 ms    │ Para análisis detallado     │
  │ NORMAL   │ 800 ms     │ Velocidad de estudio        │
  │ FAST     │ 250 ms     │ Para observar patrones      │
  │ TURBO    │ 80 ms      │ Para pruebas de rendimiento │
  └──────────┴────────────┴─────────────────────────────┘
"""

from PySide6.QtCore import QObject, QTimer, Signal


class SimClock(QObject):
    """
    Reloj central de la simulación basado en QTimer.

    Emite la señal `tick_fired(int)` en cada tick con el número
    de tick actual. El engine y la UI se conectan a esta señal.

    Uso típico:
        clock = SimClock(speed_ms=500)
        clock.tick_fired.connect(engine.tick)
        clock.tick_fired.connect(window.refresh_ui)
        clock.start()
    """

    # Señal emitida en cada tick, con el número de tick actual
    # El engine y los widgets se suscriben a esta señal
    tick_fired = Signal(int)

    # Velocidades predefinidas (en milisegundos)
    SPEED_SLOW   = 2000
    SPEED_NORMAL = 800
    SPEED_FAST   = 250
    SPEED_TURBO  = 80

    def __init__(self, speed_ms: int = SPEED_NORMAL, parent=None):
        super().__init__(parent)
        self._tick_count: int = 0
        self._speed_ms: int = max(50, speed_ms)  # Mínimo 50ms

        # QTimer: dispara timeout() cada N milisegundos
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)

    # ── Propiedades ───────────────────────────────────────────────────────────

    @property
    def tick_count(self) -> int:
        """Número total de ticks desde el inicio (o último reset)."""
        return self._tick_count

    @property
    def speed_ms(self) -> int:
        """Milisegundos entre ticks."""
        return self._speed_ms

    @property
    def is_running(self) -> bool:
        """True si el reloj está activo."""
        return self._timer.isActive()

    # ── Control ───────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Inicia o reanuda el reloj."""
        if not self._timer.isActive():
            self._timer.start(self._speed_ms)

    def pause(self) -> None:
        """Pausa el reloj. El tick_count no se reinicia."""
        self._timer.stop()

    def reset(self) -> None:
        """Detiene el reloj y reinicia el contador a cero."""
        self._timer.stop()
        self._tick_count = 0

    def set_speed(self, speed_ms: int) -> None:
        """
        Cambia la velocidad del reloj en tiempo real.

        Args:
            speed_ms: Milisegundos entre ticks (mayor = más lento)
        """
        self._speed_ms = max(50, speed_ms)
        # Si estaba corriendo, reiniciar con nueva velocidad
        if self._timer.isActive():
            self._timer.stop()
            self._timer.start(self._speed_ms)

    # ── Privado ───────────────────────────────────────────────────────────────

    def _on_timer(self) -> None:
        """Callback interno del QTimer: avanza el contador y emite la señal."""
        self._tick_count += 1
        self.tick_fired.emit(self._tick_count)
