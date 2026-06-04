"""
ui/widgets/metrics_widget.py — PatatOS Simulation Metrics dashboard.

Displays 8 metric cards in a responsive grid:
    CPU Utilization  |  Throughput        |  Avg Turnaround  |  Avg Waiting
    Avg Response     |  Context Switches  |  Starvation Evts |  Error Rate

Each card shows a large numeric value with a label below.
Cards are colour-coded green/orange/red according to quality thresholds.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.styles import Colors


# ── Thresholds & metadata for each metric ─────────────────────────────────────
# Each entry: (dict_key, display_label, unit, good_threshold, bad_threshold,
#              higher_is_better)
_METRICS: list[tuple] = [
    ("cpu_utilization",    "CPU Utilization",    "%",  80.0,  40.0,  True),
    ("throughput",         "Throughput",         "p/s", 1.0,   0.1,  True),
    ("avg_turnaround",     "Avg Turnaround",     "t",   50.0, 200.0, False),
    ("avg_waiting",        "Avg Waiting",        "t",   20.0, 100.0, False),
    ("avg_response",       "Avg Response",       "t",   10.0,  60.0, False),
    ("context_switches",   "Context Switches",   "",   50.0, 200.0,  False),
    ("starvation_events",  "Starvation Events",  "",    0.0,   5.0,  False),
    ("error_rate",         "Error Rate",         "%",   0.0,   5.0,  False),
]

# Colour for good / medium / bad
_C_GOOD   = "#16a34a"   # green
_C_MED    = "#d97706"   # orange
_C_BAD    = "#dc2626"   # red
_C_NEUT   = Colors.TEXT_SEC  # neutral (not enough data)


def _value_color(value: float, good: float, bad: float, higher: bool) -> str:
    """Return a hex colour based on whether value is good, medium, or bad."""
    if higher:
        if value >= good:
            return _C_GOOD
        if value <= bad:
            return _C_BAD
        return _C_MED
    else:
        if value <= good:
            return _C_GOOD
        if value >= bad:
            return _C_BAD
        return _C_MED


# ── Individual metric card ─────────────────────────────────────────────────────

class _MetricCard(QFrame):
    """A card showing a single metric: big value + label below."""

    def __init__(self, label: str, unit: str, parent=None):
        super().__init__(parent)
        self._unit  = unit
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
            QLabel {{ background: transparent; }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        self._value_lbl = QLabel("—")
        self._value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_lbl.setStyleSheet(
            f"color:{Colors.TEXT_MUTED}; font-size:12pt; font-weight:700;"
        )

        self._label_lbl = QLabel(label)
        self._label_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label_lbl.setStyleSheet(
            f"color:{Colors.TEXT_MUTED}; font-size:7pt; font-weight:500;"
        )
        self._label_lbl.setWordWrap(True)

        layout.addStretch()
        layout.addWidget(self._value_lbl)
        layout.addWidget(self._label_lbl)
        layout.addStretch()

    def set_value(self, value: float | None, color: str) -> None:
        if value is None:
            self._value_lbl.setText("—")
            self._value_lbl.setStyleSheet(
                f"color:{Colors.TEXT_MUTED}; font-size:12pt; font-weight:700;"
            )
        else:
            # Format: show 2 decimal for small floats, integer otherwise
            if self._unit == "%" or isinstance(value, float):
                text = f"{value:.1f}{self._unit}"
            else:
                text = f"{int(value)}{self._unit}"
            self._value_lbl.setText(text)
            self._value_lbl.setStyleSheet(
                f"color:{color}; font-size:12pt; font-weight:700;"
            )

        # Highlight card border with the same colour
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {Colors.BG_CARD};
                border: 1px solid {color if value is not None else Colors.BORDER};
                border-radius: 8px;
            }}
            QLabel {{ background: transparent; }}
            """
        )


# ── Main widget ────────────────────────────────────────────────────────────────

class MetricsWidget(QWidget):
    """
    8-card metrics dashboard.

    Usage::

        widget = MetricsWidget()
        widget.update(metrics)

    ``metrics`` – dict with optional float keys (see _METRICS for key names):
        cpu_utilization   (0–100 %)
        throughput        (processes / second)
        avg_turnaround    (ticks)
        avg_waiting       (ticks)
        avg_response      (ticks)
        context_switches  (count)
        starvation_events (count)
        error_rate        (0–100 %)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        hdr = QLabel("📊 Simulation Metrics")
        hdr.setStyleSheet(
            f"color:{Colors.ACCENT_LIGHT}; font-size:10pt; font-weight:700;"
        )
        root.addWidget(hdr)

        # 4 × 2 grid of cards
        grid = QGridLayout()
        grid.setSpacing(8)
        root.addLayout(grid)

        self._cards: dict[str, _MetricCard] = {}
        for idx, (key, label, unit, *_rest) in enumerate(_METRICS):
            card = _MetricCard(label, unit)
            self._cards[key] = card
            grid.addWidget(card, idx // 4, idx % 4)

        root.addStretch()

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, metrics: dict) -> None:  # type: ignore[override]
        """
        Refresh all metric cards.

        :param metrics: dict mapping metric keys to float values.
        """
        for key, _label, _unit, good, bad, higher in _METRICS:
            card = self._cards[key]
            raw  = metrics.get(key)
            if raw is None:
                card.set_value(None, Colors.TEXT_MUTED)
            else:
                value = float(raw)
                color = _value_color(value, good, bad, higher)
                card.set_value(value, color)
