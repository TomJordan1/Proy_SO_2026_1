"""
ui/widgets/queue_widget.py: visualizador de cola de espera y listo para PatatOS.

Muestra: 
• Colas listas: una columna por núcleo de CPU, cada proceso como un chip de color. 
• Cola de espera: procesos bloqueados en E/S, mostrados con dispositivo + ticks restantes.

Cada chip muestra: nombre del proceso, tipo de placa, prioridad, tiempo de espera.
Todo el widget está envuelto en un QScrollArea por lo que maneja muchos procesos de forma limpia.
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
    Una tarjeta compacta para un solo proceso en una cola.

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
                border-radius: 4px;
            }}
            QLabel {{ background: transparent; }}
            """
        )
        self.setFixedWidth(130)
        self.setFixedHeight(48)
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(4, 2, 4, 2)

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

        # Si este es un proceso en espera, muestra el device + remaining
        device = proc.get("device")
        remaining = proc.get("remaining_ticks")
        if device:
            bot.addWidget(_mini(f"🖧 {device}"))
        if remaining is not None:
            bot.addWidget(_mini(f"⏱ {remaining}t"))

        bot.addStretch()
        layout.addLayout(bot)


# ── Constructor de columnas ────────────────────────────────────────────────────────────

class _QueueColumn(QGroupBox):
    """Una columna QGroupBox horizontal llena de chips de proceso, persistente."""
    def __init__(self, title: str, accent: str, parent=None):
        super().__init__(title, parent)
        self.accent = accent
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
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
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll.setFixedHeight(75)
        
        self.inner_widget = QWidget()
        self.inner_widget.setStyleSheet("background: transparent;")
        self.h_layout = QHBoxLayout(self.inner_widget)
        self.h_layout.setSpacing(6)
        self.h_layout.setContentsMargins(4, 4, 4, 4)
        self.h_layout.setAlignment(Qt.AlignTop)

        self.scroll.setWidget(self.inner_widget)
        
        box_layout = QVBoxLayout(self)
        box_layout.setContentsMargins(4, 16, 4, 4)
        box_layout.addWidget(self.scroll)

    def update_processes(self, processes: list[dict]):
        # Guardar posición actual
        bar = self.scroll.horizontalScrollBar()
        old_val = bar.value()

        # Limpiar
        while self.h_layout.count():
            item = self.h_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        # Rellenar
        if not processes:
            empty = QLabel("(empty)")
            empty.setStyleSheet(
                f"color:{Colors.TEXT_MUTED}; font-size:8pt; font-style:italic;"
            )
            empty.setAlignment(Qt.AlignCenter)
            self.h_layout.addWidget(empty)
        else:
            for proc in processes:
                chip = _ProcessChip(proc, self.accent)
                self.h_layout.addWidget(chip)

        self.h_layout.addStretch()

        # Restaurar posición tras el layout
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: bar.setValue(old_val))


# ── Main widget ───────────────────────────────────────────────────────────────

class QueueWidget(QWidget):
    """
    Ready + Waiting queue visualizer.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(8)
        self._layout.setContentsMargins(0, 0, 0, 0)
        
        self._ready_columns: list[_QueueColumn] = []
        self._wait_col: _QueueColumn = None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _clear_all(self) -> None:
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
        self._ready_columns.clear()
        self._wait_col = None

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, ready_queues: list[list[dict]], waiting: list[dict]) -> None:  # type: ignore[override]
        """
        Refresh ready and waiting queue displays.
        """
        # Rebuild layout only if number of cores changed or uninitialized
        if len(self._ready_columns) != len(ready_queues) or not self._ready_columns:
            self._clear_all()
            
            # Ready Header
            ready_hdr = QLabel("⚙ Ready Queues")
            ready_hdr.setStyleSheet(
                f"color:{Colors.STATE_READY}; font-size:9pt; font-weight:700;"
            )
            self._layout.addWidget(ready_hdr)

            # Ready Columns
            ready_row = QHBoxLayout()
            ready_row.setSpacing(6)
            for i in range(len(ready_queues)):
                accent = Colors.CORE_COLORS[i % len(Colors.CORE_COLORS)]
                col = _QueueColumn(f"Core {i}", accent)
                self._ready_columns.append(col)
                ready_row.addWidget(col)
            self._layout.addLayout(ready_row)

            # Divider
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet(f"color:{Colors.BORDER};")
            self._layout.addWidget(line)

            # Wait Header
            wait_hdr = QLabel("⏳ Waiting / Blocked")
            wait_hdr.setStyleSheet(
                f"color:{Colors.STATE_WAITING}; font-size:9pt; font-weight:700;"
            )
            self._layout.addWidget(wait_hdr)
            
            # Wait Column
            self._wait_col = _QueueColumn("Waiting Queue", Colors.STATE_WAITING)
            self._layout.addWidget(self._wait_col)
            
            self._layout.addStretch()

        # Update data without recreating structural widgets
        for i, queue in enumerate(ready_queues):
            self._ready_columns[i].update_processes(queue)
            
        if self._wait_col:
            self._wait_col.update_processes(waiting)
