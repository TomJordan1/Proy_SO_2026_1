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


# ── Constantes del diagrama de estado ────────────────────────────────────────────────────

_STATE_MAP = {
    "NEW":        "NUEVO",
    "READY":      "PREPARADO",
    "RUNNING":    "EJECUCIÓN",
    "WAITING":    "BLOQUEADO",
    "TERMINATED": "TERMINADO",
    "ERROR":      "ERROR",
}

# Posiciones de los nodos de estado (normalizadas 0-1 en un lienzo de 500x260)
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

_ACTIVE_COLOR  = "#00E5A0"   # verde vivo – nodo activo
_PAST_COLOR    = "#4A90D9"   # azul - visitado anteriormente (uso futuro opcional)
_IDLE_COLOR    = "#2A2A3E"   # oscuro - relleno de nodo inactivo
_EDGE_COLOR    = "#666688"
_LABEL_COLOR   = "#AAAACC"


class _StateDiagram(QWidget):
    """Paints the 5-state process diagram and highlights the current state."""

    # Tamaño de elipse: se calcula a partir del ancho real del texto (vía
    # QFontMetrics) más este padding, con un mínimo para que ningún nodo
    # quede demasiado pequeño (p.ej. "ERROR" o "NUEVO").
    NODE_PAD_X = 18
    NODE_PAD_Y = 10
    NODE_MIN_W = 64
    NODE_MIN_H = 34

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "NEW"
        self._pulse  = 0.0
        self._timer  = QTimer(self)
        self._timer.timeout.connect(self._tick_pulse)
        self._timer.start(40)  # ~25 fps
        self.setMinimumSize(560, 320)

        # Fuente de referencia para medir texto (bold, peor caso de ancho,
        # así el nodo nunca cambia de tamaño al activarse/desactivarse).
        self._node_font = QFont()
        self._node_font.setPointSize(8)
        self._node_font.setBold(True)

    def _tick_pulse(self):
        self._pulse = (self._pulse + 0.08) % (2 * math.pi)
        self.update()

    def set_state(self, state: str):
        self._state = state.upper()
        self.update()

    def _node_center(self, name: str, w: int, h: int) -> QPointF:
        nx, ny = _NODES[name]
        return QPointF(nx * w, ny * h)

    def _node_half_size(self, label_text: str, fm) -> tuple[float, float]:
        """Calcula (semi-ancho, semi-alto) de la elipse para que el texto entre."""
        text_w = fm.horizontalAdvance(label_text)
        full_w = max(self.NODE_MIN_W, text_w + 2 * self.NODE_PAD_X)
        full_h = max(self.NODE_MIN_H, fm.height() + 2 * self.NODE_PAD_Y)
        return full_w / 2, full_h / 2

    @staticmethod
    def _ellipse_boundary_point(cx: float, cy: float, a: float, b: float,
                                 ux: float, uy: float) -> QPointF:
        """
        Punto sobre el borde de una elipse (centro cx,cy; semiejes a,b)
        en la dirección (ux,uy) que llega desde afuera hacia el centro.

        Resuelve t en: (t*ux/a)^2 + (t*uy/b)^2 = 1
        """
        denom = math.sqrt((ux / a) ** 2 + (uy / b) ** 2) if (a and b) else 0
        if denom == 0:
            return QPointF(cx, cy)
        t = 1.0 / denom
        return QPointF(cx - ux * t, cy - uy * t)

    def paintEvent(self, _event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()

        painter.fillRect(0, 0, W, H, QColor(Colors.BG_SURFACE))

        fm = painter.fontMetrics()
        painter.setFont(self._node_font)
        fm = painter.fontMetrics()  # métricas reales de la fuente de nodo

        # ── Precalcular geometría de todos los nodos (centro + semiejes) ───────
        node_geo: dict[str, tuple[float, float, float, float]] = {}
        for name in _NODES:
            label_text = _STATE_MAP.get(name, name)
            center = self._node_center(name, W, H)
            half_w, half_h = self._node_half_size(label_text, fm)
            node_geo[name] = (center.x(), center.y(), half_w, half_h)

        # ── Draw edges ───────────────────────────────────────────────────────
        for frm, to, label, cy_off in _EDGES:
            cx1, cy1, a1, b1 = node_geo[frm]
            cx2, cy2, a2, b2 = node_geo[to]
            p1 = QPointF(cx1, cy1)
            p2 = QPointF(cx2, cy2)

            pen = QPen(QColor(_EDGE_COLOR), 1.5)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)

            if cy_off != 0:
                mid = QPointF((p1.x() + p2.x()) / 2,
                              (p1.y() + p2.y()) / 2 + cy_off)
                path = QPainterPath(p1)
                path.quadTo(mid, p2)
                painter.drawPath(path)
                dx = p2.x() - mid.x()
                dy = p2.y() - mid.y()
            else:
                painter.drawLine(p1, p2)
                dx = p2.x() - p1.x()
                dy = p2.y() - p1.y()

            length = math.hypot(dx, dy) or 1
            ux, uy = dx / length, dy / length

            # Punto de llegada de la flecha: borde real de la elipse destino,
            # no un radio fijo — así funciona aunque cada nodo tenga otro tamaño.
            tip = self._ellipse_boundary_point(cx2, cy2, a2, b2, ux, uy)

            ah, aw = 8, 5
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

            mid_x = (p1.x() + p2.x()) / 2
            mid_y = (p1.y() + p2.y()) / 2 + cy_off * 0.4
            painter.setPen(QColor(_LABEL_COLOR))
            edge_font = QFont()
            edge_font.setPointSize(7)
            painter.setFont(edge_font)
            painter.drawText(
                QRectF(mid_x - 45, mid_y - 16, 90, 32),
                Qt.AlignCenter, label,
            )

        # ── Dibujar nodos (elipses) ─────────────────────────────────────────────
        pulse_factor = 1.0 + 0.06 * math.sin(self._pulse)

        for name in _NODES:
            cx, cy, half_w, half_h = node_geo[name]
            is_active = (name == self._state)

            if is_active:
                glow_w, glow_h = half_w * pulse_factor * 1.35, half_h * pulse_factor * 1.5
                grad = QRadialGradient(cx, cy, max(glow_w, glow_h))
                grad.setColorAt(0.0, QColor(_ACTIVE_COLOR + "55"))
                grad.setColorAt(1.0, QColor(_ACTIVE_COLOR + "00"))
                painter.setBrush(QBrush(grad))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QRectF(cx - glow_w, cy - glow_h, glow_w * 2, glow_h * 2))

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

            painter.drawEllipse(QRectF(cx - half_w, cy - half_h, half_w * 2, half_h * 2))

            # Label DENTRO de la elipse — ya cabe porque la elipse se dimensionó
            # a partir del ancho real de este mismo texto.
            label_text = _STATE_MAP.get(name, name)
            label_font = QFont(self._node_font)
            label_font.setBold(is_active)
            painter.setFont(label_font)
            painter.setPen(QColor(_ACTIVE_COLOR if is_active else "#CCCCEE"))
            painter.drawText(
                QRectF(cx - half_w, cy - half_h, half_w * 2, half_h * 2),
                Qt.AlignCenter, label_text,
            )


# ── tarjeta de campo ────────────────────────────────────────────────────────────────

def _field_row(label: str, value: Any) -> tuple[QHBoxLayout, QLabel]:
    row = QHBoxLayout()
    lbl = QLabel(f"{label}:")
    lbl.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:8pt; min-width:140px;")
    lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    val_str = "—" if value is None or value == -1 else str(value)
    val = QLabel(val_str)
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

        # ── Diagrama de estadpo ─────────────────────────────────────────────────────
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

        # Inyectar finish_time matemáticamente si no viene del backend
        if proc.get("state") == "TERMINATED" and "finish_time" not in proc:
            arr = proc.get("arrival_tick", proc.get("arrival_time", 0))
            turn = proc.get("turnaround_time", proc.get("turnaround", 0))
            if turn > 0:
                proc["finish_time"] = arr + turn

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


        # ── Boton de cierre ──────────────────────────────────────────────────────
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
