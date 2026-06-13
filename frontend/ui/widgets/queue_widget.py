"""
ui/widgets/queue_widget.py — PatatOS Ready & Waiting Queue visualizer.

Shows:
  • Ready queues – one column per CPU core, each process as a colored chip.
  • Waiting queue – processes blocked on I/O, shown with device + remaining ticks.

Each chip displays: process name, type badge, priority, waiting time.
The whole widget is wrapped in a QScrollArea so it handles many processes cleanly.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.styles import Colors, TYPE_COLORS, pid_color


# ── Chip ──────────────────────────────────────────────────────────────────────

class _ProcessChip(QFrame):
    """
    A compact card for a single process in a queue.

    Expected dict keys (all optional):
        name, pid, type, priority, waiting_time, device, remaining_ticks
    """

    def __init__(self, proc: dict, accent: str = Colors.ACCENT, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        pid    = proc.get("pid", 0)
        color  = pid_color(int(pid)) if pid else accent
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {Colors.BG_CARD};
                border: 1px solid {color};
                border-left: 3px solid {color};
                border-radius: 5px;
            }}
            QLabel {{ background: transparent; }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(6, 4, 6, 4)

        # ── Top row: name + type badge ─────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(4)

        name = proc.get("name") or proc.get("process_name") or "?"
        name_lbl = QLabel(f"{name}")
        name_lbl.setStyleSheet(
            f"color:{Colors.TEXT_PRIMARY}; font-size:8pt; font-weight:700;"
        )
        top.addWidget(name_lbl)

        proc_type = (proc.get("type") or "").upper()
        type_color = TYPE_COLORS.get(proc_type, Colors.TEXT_MUTED)
        if proc_type:
            badge = QLabel(proc_type[:3])          # abbrev to 3 chars
            badge.setStyleSheet(
                f"background:{type_color}22; color:{type_color};"
                " border-radius:3px; font-size:7pt; font-weight:700; padding:0 3px;"
            )
            top.addWidget(badge)
        top.addStretch()
        layout.addLayout(top)

        # ── Bottom row: PID · priority · wait time ────────────────────────────
        bot = QHBoxLayout()
        bot.setSpacing(8)

        def _mini(text: str) -> QLabel:
            l = QLabel(text)
            l.setStyleSheet(
                f"color:{Colors.TEXT_MUTED}; font-size:7pt;"
            )
            return l

        bot.addWidget(_mini(f"PID {pid}"))
        prio = proc.get("priority")
        if prio is not None:
            bot.addWidget(_mini(f"P:{prio}"))
        wait = proc.get("waiting_time")
        if wait is not None:
            bot.addWidget(_mini(f"W:{wait}t"))

        # If this is a waiting process, show device + remaining
        device = proc.get("device")
        remaining = proc.get("remaining_ticks")
        if device:
            bot.addWidget(_mini(f"🖧 {device}"))
        if remaining is not None:
            bot.addWidget(_mini(f"⏱ {remaining}t"))

        bot.addStretch()
        layout.addLayout(bot)


# ── Column builder ────────────────────────────────────────────────────────────

def _build_queue_column(title: str, processes: list[dict], accent: str) -> QGroupBox:
    """Return a vertical QGroupBox column filled with process chips."""
    box = QGroupBox(title)
    box.setStyleSheet(
        f"""
        QGroupBox {{
            border: 1px solid {accent};
            border-radius: 6px;
            margin-top: 14px;
            padding: 6px 4px 4px 4px;
            background: {Colors.BG_SURFACE};
            color: {Colors.TEXT_PRIMARY};
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px; top: 0px;
            padding: 0 4px;
            color: {accent};
            font-size: 9pt;
        }}
        """
    )
    layout = QVBoxLayout(box)
    layout.setSpacing(4)
    layout.setContentsMargins(4, 6, 4, 4)

    if not processes:
        empty = QLabel("(empty)")
        empty.setStyleSheet(
            f"color:{Colors.TEXT_MUTED}; font-size:8pt; font-style:italic;"
        )
        empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(empty)
    else:
        for proc in processes:
            chip = _ProcessChip(proc, accent)
            layout.addWidget(chip)

    layout.addStretch()
    return box


# ── Main widget ───────────────────────────────────────────────────────────────

class QueueWidget(QWidget):
    """
    Ready + Waiting queue visualizer.

    Usage::

        widget = QueueWidget()
        widget.update(ready_queues, waiting)

    ``ready_queues`` – list of lists (one inner list per CPU core).
    ``waiting``      – flat list of dicts for blocked processes.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(0, 0, 0, 0)

        # Scroll area wraps everything
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background:{Colors.BG_BASE}; border:none; }}"
        )
        root.addWidget(self._scroll)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setSpacing(8)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._scroll.setWidget(self._container)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _clear(self) -> None:
        def clear_layout(layout):
            if layout is not None:
                while layout.count():
                    item = layout.takeAt(0)
                    widget = item.widget()
                    if widget is not None:
                        widget.deleteLater()
                    else:
                        clear_layout(item.layout())
        clear_layout(self._layout)

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, ready_queues: list[list[dict]], waiting: list[dict]) -> None:  # type: ignore[override]
        """
        Refresh ready and waiting queue displays.

        :param ready_queues: list of process lists, one per core.
        :param waiting:      flat list of waiting/blocked process dicts.
        """
        self._clear()

        # ── Ready queues section ──────────────────────────────────────────────
        ready_hdr = QLabel("⚙ Ready Queues")
        ready_hdr.setStyleSheet(
            f"color:{Colors.STATE_READY}; font-size:9pt; font-weight:700;"
        )
        self._layout.addWidget(ready_hdr)

        ready_row = QHBoxLayout()
        ready_row.setSpacing(6)

        if not ready_queues:
            none_lbl = QLabel("No ready queues")
            none_lbl.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:8pt;")
            ready_row.addWidget(none_lbl)
        else:
            for i, queue in enumerate(ready_queues):
                accent = Colors.CORE_COLORS[i % len(Colors.CORE_COLORS)]
                col = _build_queue_column(f"Core {i}", queue, accent)
                col.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                ready_row.addWidget(col)

        self._layout.addLayout(ready_row)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color:{Colors.BORDER};")
        self._layout.addWidget(line)

        # ── Waiting queue section ─────────────────────────────────────────────
        wait_hdr = QLabel("⏳ Waiting / Blocked")
        wait_hdr.setStyleSheet(
            f"color:{Colors.STATE_WAITING}; font-size:9pt; font-weight:700;"
        )
        self._layout.addWidget(wait_hdr)

        if not waiting:
            empty_lbl = QLabel("No blocked processes")
            empty_lbl.setStyleSheet(
                f"color:{Colors.TEXT_MUTED}; font-size:8pt; font-style:italic;"
            )
            self._layout.addWidget(empty_lbl)
        else:
            wait_col = _build_queue_column(
                "Waiting Queue", waiting, Colors.STATE_WAITING
            )
            self._layout.addWidget(wait_col)

        self._layout.addStretch()
