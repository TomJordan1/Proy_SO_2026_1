"""
ui/widgets/pcb_detail_dialog.py — Inspector Detallado de la PCB de un Proceso.

Muestra:
  - Todos los campos de la PCB del proceso seleccionado.
  - Diagrama gráfico de los 5 estados del SO con el estado actual resaltado,
    siguiendo la topología clásica:
      nuevo → preparado ↔ ejecución → terminado
                ↑              ↓
             bloqueado ←────────
"""
from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter,
    QPainterPath, QPen, QRadialGradient,
)
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from ui.styles import Colors, STATE_COLORS


# ── State diagram constants ────────────────────────────────────────────────────

_STATE_MAP = {
    "NEW":        "NUEVO",
    "READY":      "PREPARADO",
    "RUNNING":    "EJECUCIÓN",
    "WAITING":    "BLOQUEADO",
    "TERMINATED": "TERMINADO",
    "ERROR":      "ERROR",
}

# State node positions (normalized 0-1 in a 500x260 canvas)
_NODES: dict[str, tuple[float, float]] = {
    "NEW":        (0.08, 0.40),
    "READY":      (0.35, 0.40),
    "RUNNING":    (0.65, 0.40),
    "WAITING":    (0.50, 0.82),
    "TERMINATED": (0.92, 0.25),
    "ERROR":      (0.92, 0.60),
}

_NODE_RADIUS = 30  # px in a 500x260 canvas

# Edges: (from, to, label, curve_y_offset)
_EDGES = [
    ("NEW",        "READY",      "admitido",              0),
    ("READY",      "RUNNING",    "planificador",         -28),
    ("RUNNING",    "READY",      "interrupción",          28),
    ("RUNNING",    "WAITING",    "llamada E/S\no evento", 0),
    ("WAITING",    "READY",      "finaliza E/S\nu evento", 0),
    ("RUNNING",    "TERMINATED", "llama sist.\no excep.", 0),
    ("RUNNING",    "ERROR",      "error fatal",           0),
]

_ACTIVE_COLOR  = "#00E5A0"   # vivid green – active node
_PAST_COLOR    = "#4A90D9"   # blue – previously visited (optional future use)
_IDLE_COLOR    = "#2A2A3E"   # dark – inactive node fill
_EDGE_COLOR    = "#666688"
_LABEL_COLOR   = "#AAAACC"


class _StateDiagram(QWidget):
    """Paints the 5-state process diagram and highlights the current state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "NEW"
        self._pulse  = 0.0
        self._timer  = QTimer(self)
        self._timer.timeout.connect(self._tick_pulse)
        self._timer.start(40)  # ~25 fps
        self.setMinimumSize(500, 260)

    def _tick_pulse(self):
        self._pulse = (self._pulse + 0.08) % (2 * math.pi)
        self.update()

    def set_state(self, state: str):
        self._state = state.upper()
        self.update()

    def _node_center(self, name: str, w: int, h: int) -> QPointF:
        nx, ny = _NODES[name]
        return QPointF(nx * w, ny * h)

    def paintEvent(self, _event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()

        # Background
        painter.fillRect(0, 0, W, H, QColor(Colors.BG_SURFACE))

        # ── Draw edges ─────────────────────────────────────────────────────────
        for frm, to, label, cy_off in _EDGES:
            p1 = self._node_center(frm, W, H)
            p2 = self._node_center(to, W, H)

            pen = QPen(QColor(_EDGE_COLOR), 1.5)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)

            if cy_off != 0:
                # Quadratic bezier
                mid = QPointF((p1.x() + p2.x()) / 2,
                              (p1.y() + p2.y()) / 2 + cy_off)
                path = QPainterPath(p1)
                path.quadTo(mid, p2)
                painter.drawPath(path)
                # Arrowhead at p2 along the path
                dx = p2.x() - mid.x()
                dy = p2.y() - mid.y()
            else:
                painter.drawLine(p1, p2)
                dx = p2.x() - p1.x()
                dy = p2.y() - p1.y()

            # Arrowhead
            length = math.hypot(dx, dy) or 1
            ux, uy = dx / length, dy / length
            ah = 8
            aw = 5
            tip = QPointF(p2.x() - ux * (_NODE_RADIUS * W / 500),
                          p2.y() - uy * (_NODE_RADIUS * H / 260))
            left = QPointF(tip.x() - ah * ux + aw * uy,
                           tip.y() - ah * uy - aw * ux)
            right = QPointF(tip.x() - ah * ux - aw * uy,
                            tip.y() - ah * uy + aw * ux)
            arrow = QPainterPath()
            arrow.moveTo(tip)
            arrow.lineTo(left)
            arrow.lineTo(right)
            arrow.closeSubpath()
            painter.fillPath(arrow, QColor(_EDGE_COLOR))

            # Edge label
            mid_x = (p1.x() + p2.x()) / 2
            mid_y = (p1.y() + p2.y()) / 2 + cy_off * 0.4
            painter.setPen(QColor(_LABEL_COLOR))
            font = QFont()
            font.setPointSize(7)
            painter.setFont(font)
            painter.drawText(
                QRectF(mid_x - 45, mid_y - 16, 90, 32),
                Qt.AlignCenter, label,
            )

        # ── Draw nodes ─────────────────────────────────────────────────────────
        node_font = QFont()
        node_font.setPointSize(8)
        node_font.setBold(True)
        painter.setFont(node_font)

        pulse_factor = 1.0 + 0.06 * math.sin(self._pulse)

        for name, (nx, ny) in _NODES.items():
            cx = nx * W
            cy = ny * H
            r  = _NODE_RADIUS * min(W, H) / 500

            is_active = (name == self._state)

            if is_active:
                # Pulsating glow
                glow_r = r * pulse_factor * 1.7
                grad = QRadialGradient(cx, cy, glow_r)
                grad.setColorAt(0.0, QColor(_ACTIVE_COLOR + "55"))
                grad.setColorAt(1.0, QColor(_ACTIVE_COLOR + "00"))
                painter.setBrush(QBrush(grad))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(
                    QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2)
                )

                # Active node border + fill
                painter.setPen(QPen(QColor(_ACTIVE_COLOR), 2))
                fill = QColor(_ACTIVE_COLOR)
                fill.setAlpha(40)
                painter.setBrush(QBrush(fill))
            elif name == "ERROR" and self._state == "ERROR":
                painter.setPen(QPen(QColor("#FF4C4C"), 2))
                fill = QColor("#FF4C4C")
                fill.setAlpha(40)
                painter.setBrush(QBrush(fill))
            else:
                painter.setPen(QPen(QColor("#555577"), 1.5))
                painter.setBrush(QBrush(QColor(_IDLE_COLOR)))

            painter.drawEllipse(
                QRectF(cx - r, cy - r, r * 2, r * 2)
            )

            # Label inside node
            label_text = _STATE_MAP.get(name, name)
            painter.setPen(QColor(_ACTIVE_COLOR if is_active else "#9999BB"))
            painter.drawText(
                QRectF(cx - r, cy - r, r * 2, r * 2),
                Qt.AlignCenter, label_text,
            )


# ── Field card ────────────────────────────────────────────────────────────────

def _field_row(label: str, value: Any) -> tuple[QHBoxLayout, QLabel]:
    row = QHBoxLayout()
    lbl = QLabel(f"{label}:")
    lbl.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:8pt; min-width:140px;")
    lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    val = QLabel(str(value) if value is not None else "—")
    val.setStyleSheet(f"color:{Colors.TEXT_PRIMARY}; font-size:8pt; font-family:monospace;")
    val.setWordWrap(True)
    row.addWidget(lbl)
    row.addWidget(val, 1)
    return row, val


# ── Dialog ────────────────────────────────────────────────────────────────────

class PCBDetailDialog(QDialog):
    """Modal que muestra la PCB completa de un proceso y el diagrama de 5 estados."""

    def __init__(self, proc: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Inspector PCB — P{proc.get('pid', '?')} ({proc.get('name', '?')})")
        self.setMinimumSize(680, 640)
        self.setModal(True)
        self.setStyleSheet(
            f"background:{Colors.BG_BASE}; color:{Colors.TEXT_PRIMARY};"
        )

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 12)

        # ── Title ─────────────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel(f"P{proc.get('pid', '?')}  {proc.get('name', '')}")
        title.setStyleSheet(
            f"color:{Colors.ACCENT_LIGHT}; font-size:13pt; font-weight:bold;"
        )
        state_str = str(proc.get("state", "UNKNOWN")).upper()
        state_color = STATE_COLORS.get(state_str, Colors.TEXT_MUTED)
        badge = QLabel(state_str)
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(24)
        badge.setStyleSheet(
            f"background:{state_color}33; color:{state_color}; border:1px solid {state_color};"
            f" border-radius:12px; padding:0 10px; font-size:8pt; font-weight:bold;"
        )
        self._title_lbl = title
        self._badge_lbl = badge
        title_row.addWidget(self._title_lbl)
        title_row.addStretch()
        title_row.addWidget(self._badge_lbl)
        root.addLayout(title_row)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"color:{Colors.BORDER};")
        root.addWidget(divider)

        # ── State diagram ─────────────────────────────────────────────────────
        diag_label = QLabel("Diagrama de 5 Estados")
        diag_label.setStyleSheet(
            f"color:{Colors.TEXT_SEC}; font-size:9pt; font-weight:600;"
        )
        root.addWidget(diag_label)

        self._diagram = _StateDiagram()
        self._diagram.set_state(state_str)
        root.addWidget(self._diagram)

        divider2 = QFrame()
        divider2.setFrameShape(QFrame.HLine)
        divider2.setStyleSheet(f"color:{Colors.BORDER};")
        root.addWidget(divider2)

        # ── PCB fields ────────────────────────────────────────────────────────
        fields_label = QLabel("Campos de la PCB")
        fields_label.setStyleSheet(
            f"color:{Colors.TEXT_SEC}; font-size:9pt; font-weight:600;"
        )
        root.addWidget(fields_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        fields_widget = QWidget()
        fields_widget.setStyleSheet("background: transparent;")
        fields_layout = QVBoxLayout(fields_widget)
        fields_layout.setSpacing(4)
        fields_layout.setContentsMargins(0, 0, 0, 0)

        self._val_labels = {}
        self._keys_map = {}

        def add(label, *keys, fmt=None, fmt_func=None):
            self._keys_map[label] = (keys, fmt, fmt_func)
            v = None
            for k in keys:
                val = proc.get(k)
                if val is not None:
                    v = val
                    break
            
            if v is not None:
                if fmt_func:
                    try: v = fmt_func(v)
                    except Exception: pass
                elif fmt:
                    try: v = fmt.format(v)
                    except Exception: pass
            
            row_layout, val_lbl = _field_row(label, v)
            self._val_labels[label] = val_lbl
            fields_layout.addLayout(row_layout)

        add("PID",                   "pid")
        add("Nombre",                "name", "process_name")
        add("Tipo de Proceso",       "process_type", "type")
        add("Estado",                "state")
        add("Prioridad",             "priority")
        add("Burst Time (ticks)",    "burst_time")
        add("Tiempo Restante",       "remaining_time", "remaining")
        add("Tiempo de Espera",      "waiting_time", "waiting")
        add("Tiempo Respuesta",      "response_time")
        add("Tiempo de Llegada",     "arrival_time", "arrival_tick")
        add("Tiempo de Fin",         "finish_time")
        add("Turnaround",            "turnaround_time")
        add("Completado (%)",        "completion", "completion_percent", fmt="{:.1f}%")

        fields_layout.addWidget(_divider())

        add("Program Counter (PC)",  "pc", "program_counter", fmt="0x{:04X}")
        add("PC (hex)",              "pc_hex")
        add("Núcleo Asignado (CPU)", "cpu_id")

        fields_layout.addWidget(_divider())

        add("Mem. Asignada (MB)",    "mem_mb", "memory_size", "memory_mb")
        add("Dir. Base Física",      "memory_base_address", fmt="0x{:04X}")
        add("Dispositivo I/O",       "io_device")

        fields_layout.addWidget(_divider())

        # Registros
        def format_regs(r):
            if isinstance(r, dict):
                return " ".join(f"{k}:0x{v:04X}" if isinstance(v, int) else f"{k}:{v}" for k,v in r.items())
            return str(r)
            
        add("Registros", "registers", fmt_func=format_regs)

        fields_layout.addWidget(_divider())

        add("Código de Error",       "error_code", "error")

        fields_layout.addStretch()
        scroll.setWidget(fields_widget)
        root.addWidget(scroll, 1)

    def update_data(self, proc: dict):
        """Actualiza la información en tiempo real sin redibujar toda la UI."""
        # 1. Update Title & Badge
        pid = proc.get('pid', '?')
        name = proc.get('name', '')
        self.setWindowTitle(f"Inspector PCB — P{pid} ({name})")
        self._title_lbl.setText(f"P{pid}  {name}")
        
        state_str = str(proc.get("state", "UNKNOWN")).upper()
        state_color = STATE_COLORS.get(state_str, Colors.TEXT_MUTED)
        self._badge_lbl.setText(state_str)
        self._badge_lbl.setStyleSheet(
            f"background:{state_color}33; color:{state_color}; border:1px solid {state_color};"
            f" border-radius:12px; padding:0 10px; font-size:8pt; font-weight:bold;"
        )
        
        # 2. Update state diagram
        self._diagram.set_state(state_str)
        
        # 3. Update all fields
        for label, (keys, fmt, fmt_func) in self._keys_map.items():
            v = None
            for k in keys:
                val = proc.get(k)
                if val is not None:
                    v = val
                    break
            
            if v is not None:
                if fmt_func:
                    try: v = fmt_func(v)
                    except Exception: pass
                elif fmt:
                    try: v = fmt.format(v)
                    except Exception: pass
                
            if label in self._val_labels:
                self._val_labels[label].setText(str(v) if v is not None else "—")


        # ── Close button ──────────────────────────────────────────────────────
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        btn_box.setStyleSheet(
            f"QPushButton {{ background:{Colors.BG_ELEVATED}; color:{Colors.TEXT_PRIMARY};"
            f" border:1px solid {Colors.BORDER}; border-radius:4px; padding:4px 16px; }}"
            f"QPushButton:hover {{ background:{Colors.ACCENT_DARK}; }}"
        )
        root.addWidget(btn_box)


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"color:{Colors.BORDER}; margin:2px 0;")
    return line
