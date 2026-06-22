"""
ui/widgets/pcb_detail_dialog.py — Inspector Detallado de la PCB de un Proceso.
"""
from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter,
    QPainterPath, QPen, QRadialGradient,
)
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame,
    QHBoxLayout, QLabel, QScrollArea,
    QVBoxLayout, QWidget,
)

from ui.styles import Colors, STATE_COLORS


_STATE_MAP = {
    "NEW":        "NUEVO",
    "READY":      "PREPARADO",
    "RUNNING":    "EJECUCIÓN",
    "WAITING":    "BLOQUEADO",
    "TERMINATED": "TERMINADO",
}

_NODES: dict[str, tuple[float, float]] = {
    "NEW":        (0.07, 0.35),
    "READY":      (0.32, 0.40),
    "RUNNING":    (0.60, 0.40),
    "WAITING":    (0.46, 0.83),
    "TERMINATED": (0.90, 0.35),
}

_EDGES = [
    ("NEW",        "READY",      "admitido",                0),
    ("READY",      "RUNNING",    "planificador",          -34),
    ("RUNNING",    "READY",      "interrupción",           34),
    ("RUNNING",    "WAITING",    "llamada E/S\no evento", -16),
    ("WAITING",    "READY",      "finaliza E/S\nu evento", 16),
    ("RUNNING",    "TERMINATED", "llama sist.\no excep.",   0),
]

_ACTIVE_COLOR       = "#00E5A0"
_PAST_COLOR         = "#4A90D9"   # borde de nodo ya visitado
_IDLE_COLOR         = "#2A2A3E"
_EDGE_COLOR_IDLE    = "#E8A33D"   # ámbar tenue — arista aún no recorrida
_EDGE_COLOR_VISITED = "#FFCB66"   # ámbar brillante — arista ya recorrida


class _StateDiagram(QWidget):
    """
    Diagrama de 5 estados con historial completo de recorrido y cometa animado.
    Las aristas se recortan al borde real de cada elipse (nunca entran al
    nodo) y usan una paleta ámbar, deliberadamente distinta de los colores
    de los nodos, para que nunca se confundan visualmente al cruzarse.
    """

    NODE_PAD_X = 14
    NODE_PAD_Y = 8
    NODE_MIN_W = 60
    NODE_MIN_H = 32
    ARROW_GAP  = 5   # separación entre el trazo y el borde real del nodo
    _TRANSITION_STEP = 0.10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state: str | None = None
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)
        self.setMinimumSize(620, 380)

        self._node_font = QFont()
        self._node_font.setPointSize(8)
        self._node_font.setBold(True)

        self._visited_nodes: set[str] = set()
        self._visited_edges: set[tuple[str, str]] = set()

        self._transition_from: str | None = None
        self._transition_to:   str | None = None
        self._transition_t: float = 1.0

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start(50)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def load_history(self, states: list[str]) -> None:
        self._visited_nodes.clear()
        self._visited_edges.clear()
        prev = None
        for s in states:
            s = s.upper()
            self._visited_nodes.add(s)
            if prev is not None and prev != s:
                self._visited_edges.add((prev, s))
            prev = s
        if states:
            self._state = states[-1].upper()
        self.update()

    def set_state(self, state: str) -> None:
        state = state.upper()
        if state == self._state:
            return
        if self._state is not None:
            self._visited_edges.add((self._state, state))
            self._transition_from = self._state
            self._transition_to   = state
            self._transition_t    = 0.0
        self._visited_nodes.add(state)
        self._state = state
        self.update()

    def _tick(self):
        self._pulse = (self._pulse + 0.06) % (2 * math.pi)
        if self._transition_t < 1.0:
            self._transition_t = min(1.0, self._transition_t + self._TRANSITION_STEP)
        self.update()

    def _node_center(self, name: str, w: int, h: int) -> QPointF:
        nx, ny = _NODES[name]
        return QPointF(nx * w, ny * h)

    def _node_half_size(self, label: str, fm) -> tuple[float, float]:
        tw = fm.horizontalAdvance(label)
        return (max(self.NODE_MIN_W, tw + 2 * self.NODE_PAD_X) / 2,
                max(self.NODE_MIN_H, fm.height() + 2 * self.NODE_PAD_Y) / 2)

    @staticmethod
    def _ellipse_boundary(cx, cy, a, b, dx, dy) -> QPointF:
        """Punto sobre el borde de la elipse, en la dirección (dx,dy) desde el centro."""
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        denom = math.sqrt((ux / a) ** 2 + (uy / b) ** 2) if (a and b) else 0
        if not denom:
            return QPointF(cx, cy)
        t = 1.0 / denom
        return QPointF(cx + ux * t, cy + uy * t)

    @staticmethod
    def _point_on_path(p1: QPointF, p2: QPointF, mid: QPointF | None, t: float) -> QPointF:
        if mid is None:
            return QPointF(p1.x() + (p2.x() - p1.x()) * t,
                           p1.y() + (p2.y() - p1.y()) * t)
        u = 1 - t
        return QPointF(u*u*p1.x() + 2*u*t*mid.x() + t*t*p2.x(),
                       u*u*p1.y() + 2*u*t*mid.y() + t*t*p2.y())

    def _draw_pill_label(self, painter: QPainter, center: QPointF, text: str, color: QColor) -> None:
        fm = painter.fontMetrics()
        lines = text.split("\n")
        line_w = max(fm.horizontalAdvance(ln) for ln in lines)
        line_h = fm.height()
        pad_x, pad_y = 6, 3
        box_w = line_w + pad_x * 2
        box_h = line_h * len(lines) + pad_y * 2
        rect = QRectF(center.x() - box_w / 2, center.y() - box_h / 2, box_w, box_h)

        bg = QColor(Colors.BG_SURFACE)
        bg.setAlpha(235)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(rect, 4, 4)

        painter.setPen(color)
        painter.drawText(rect, Qt.AlignCenter, text)

    def paintEvent(self, _event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        painter.fillRect(0, 0, W, H, QColor(Colors.BG_SURFACE))

        painter.setFont(self._node_font)
        fm = painter.fontMetrics()

        geo: dict[str, tuple[float, float, float, float]] = {}
        for name in _NODES:
            c = self._node_center(name, W, H)
            hw, hh = self._node_half_size(_STATE_MAP.get(name, name), fm)
            geo[name] = (c.x(), c.y(), hw, hh)

        # ── Aristas ───────────────────────────────────────────────────────────
        comet_geo = None
        for frm, to, label, cy_off in _EDGES:
            cx1, cy1, a1, b1 = geo[frm]
            cx2, cy2, a2, b2 = geo[to]
            p1c, p2c = QPointF(cx1, cy1), QPointF(cx2, cy2)

            traveled = (frm, to) in self._visited_edges
            edge_color = QColor(_EDGE_COLOR_VISITED if traveled else _EDGE_COLOR_IDLE)

            if cy_off:
                mid = QPointF((p1c.x()+p2c.x())/2, (p1c.y()+p2c.y())/2 + cy_off)
                sdx, sdy = mid.x()-p1c.x(), mid.y()-p1c.y()   # tangente al salir de p1
                edx, edy = p2c.x()-mid.x(), p2c.y()-mid.y()   # tangente al llegar a p2
            else:
                mid = None
                sdx, sdy = p2c.x()-p1c.x(), p2c.y()-p1c.y()
                edx, edy = sdx, sdy

            s_len = math.hypot(sdx, sdy) or 1
            sux, suy = sdx / s_len, sdy / s_len
            e_len = math.hypot(edx, edy) or 1
            eux, euy = edx / e_len, edy / e_len

            # Puntos RECORTADOS al borde real de cada elipse — esto es lo que
            # impide que la línea entre o atraviese cualquier nodo.
            start_b = self._ellipse_boundary(cx1, cy1, a1, b1, sux, suy)
            start_pt = QPointF(start_b.x() + sux*self.ARROW_GAP, start_b.y() + suy*self.ARROW_GAP)

            end_b = self._ellipse_boundary(cx2, cy2, a2, b2, -eux, -euy)
            tip = QPointF(end_b.x() - eux*self.ARROW_GAP, end_b.y() - euy*self.ARROW_GAP)

            # Halo oscuro detrás del trazo: lo hace legible sobre cualquier
            # fondo, incluido el relleno semitransparente de los nodos.
            halo_pen = QPen(QColor(Colors.BG_SURFACE), (2.2 if traveled else 1.5) + 2.6)
            halo_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(halo_pen)
            painter.setBrush(Qt.NoBrush)
            if mid is not None:
                halo_path = QPainterPath(start_pt); halo_path.quadTo(mid, tip)
                painter.drawPath(halo_path)
            else:
                painter.drawLine(start_pt, tip)

            pen = QPen(edge_color, 2.2 if traveled else 1.5)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            if mid is not None:
                path = QPainterPath(start_pt); path.quadTo(mid, tip)
                painter.drawPath(path)
            else:
                painter.drawLine(start_pt, tip)

            ah, aw = 8, 5
            arrow = QPainterPath()
            arrow.moveTo(tip)
            arrow.lineTo(tip.x()-ah*eux+aw*euy, tip.y()-ah*euy-aw*eux)
            arrow.lineTo(tip.x()-ah*eux-aw*euy, tip.y()-ah*euy+aw*eux)
            arrow.closeSubpath()
            painter.setPen(Qt.NoPen)
            painter.fillPath(arrow, edge_color)

            label_center = QPointF((p1c.x()+p2c.x())/2, (p1c.y()+p2c.y())/2 + cy_off*0.4)
            ef = QFont(); ef.setPointSize(7)
            painter.setFont(ef)
            self._draw_pill_label(painter, label_center, label, edge_color)
            painter.setFont(self._node_font)

            if frm == self._transition_from and to == self._transition_to:
                comet_geo = (start_pt, tip, mid)

        # ── Nodos ─────────────────────────────────────────────────────────────
        pf = 1.0 + 0.06 * math.sin(self._pulse)
        for name in _NODES:
            cx, cy, hw, hh = geo[name]
            active   = (name == self._state)
            visited  = (name in self._visited_nodes) and not active

            if active:
                gw, gh = hw*pf*1.35, hh*pf*1.5
                grad = QRadialGradient(cx, cy, max(gw, gh))
                grad.setColorAt(0.0, QColor(_ACTIVE_COLOR+"55"))
                grad.setColorAt(1.0, QColor(_ACTIVE_COLOR+"00"))
                painter.setBrush(QBrush(grad))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QRectF(cx-gw, cy-gh, gw*2, gh*2))
                painter.setPen(QPen(QColor(_ACTIVE_COLOR), 2))
                fill = QColor(_ACTIVE_COLOR); fill.setAlpha(55)
                painter.setBrush(QBrush(fill))
            elif visited:
                painter.setPen(QPen(QColor(_PAST_COLOR), 1.8))
                fill = QColor(_PAST_COLOR); fill.setAlpha(45)
                painter.setBrush(QBrush(fill))
            else:
                painter.setPen(QPen(QColor("#555577"), 1.5))
                painter.setBrush(QBrush(QColor(_IDLE_COLOR)))

            painter.drawEllipse(QRectF(cx-hw, cy-hh, hw*2, hh*2))

            lf = QFont(self._node_font); lf.setBold(active)
            painter.setFont(lf)
            if active:
                tc = QColor(_ACTIVE_COLOR)
            elif visited:
                tc = QColor(_PAST_COLOR)
            else:
                tc = QColor("#9999BB")
            painter.setPen(tc)
            painter.drawText(QRectF(cx-hw, cy-hh, hw*2, hh*2),
                             Qt.AlignCenter, _STATE_MAP.get(name, name))

        # ── Cometa ────────────────────────────────────────────────────────────
        if comet_geo and self._transition_t < 1.0:
            p1, p2, mid = comet_geo
            t = self._transition_t
            for i, dt in enumerate((0.0, 0.06, 0.12, 0.18)):
                tt = max(0.0, t - dt)
                pt = self._point_on_path(p1, p2, mid, tt)
                alpha = max(0, 220 - i*55)
                r = 6 - i*1.1
                c = QColor("#FFFFFF" if i == 0 else _ACTIVE_COLOR)
                c.setAlpha(alpha)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(c))
                painter.drawEllipse(QRectF(pt.x()-r, pt.y()-r, r*2, r*2))

        # ── Leyenda ───────────────────────────────────────────────────────────
        lf2 = QFont(); lf2.setPointSize(7)
        painter.setFont(lf2)
        lx, ly = W-130, 12
        for ch, txt in ((_ACTIVE_COLOR,        "Estado actual"),
                        (_PAST_COLOR,           "Visitado"),
                        ("#555577",             "No visitado"),
                        (_EDGE_COLOR_VISITED,   "Transición")):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(ch)))
            painter.drawEllipse(QRectF(lx, ly+2, 8, 8))
            painter.setPen(QColor("#AAAACC"))
            painter.drawText(QRectF(lx+12, ly-2, 110, 16),
                             Qt.AlignVCenter|Qt.AlignLeft, txt)
            ly += 16


# ── helpers ───────────────────────────────────────────────────────────────────

def _field_row(label: str, value: Any) -> tuple[QHBoxLayout, QLabel]:
    row = QHBoxLayout()
    lbl = QLabel(f"{label}:")
    lbl.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:8pt; min-width:140px;")
    lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    val_str = "—" if value is None or value == -1 else str(value)
    val = QLabel(val_str)
    val.setStyleSheet(
        f"color:{Colors.TEXT_PRIMARY}; font-size:8pt; font-family:monospace;")
    val.setWordWrap(True)
    row.addWidget(lbl)
    row.addWidget(val, 1)
    return row, val


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"color:{Colors.BORDER}; margin:2px 0;")
    return line


# ── Dialog ────────────────────────────────────────────────────────────────────

class PCBDetailDialog(QDialog):
    """Modal que muestra la PCB completa de un proceso y el diagrama de 5 estados."""

    def __init__(self, proc: dict, parent=None):
        super().__init__(parent)
        pid_str  = proc.get('pid', '?')
        name_str = proc.get('name', '?')
        self.setWindowTitle(f"Inspector PCB — P{pid_str} ({name_str})")
        self.setMinimumSize(680, 640)
        self.setModal(True)
        self.setStyleSheet(
            f"background:{Colors.BG_BASE}; color:{Colors.TEXT_PRIMARY};")

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 12)

        # Título + badge ───────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        self._title_lbl = QLabel(f"P{pid_str}  {name_str}")
        self._title_lbl.setStyleSheet(
            f"color:{Colors.ACCENT_LIGHT}; font-size:13pt; font-weight:bold;")
        state_str   = str(proc.get("state", "UNKNOWN")).upper()
        state_color = STATE_COLORS.get(state_str, Colors.TEXT_MUTED)
        self._badge_lbl = QLabel(state_str)
        self._badge_lbl.setAlignment(Qt.AlignCenter)
        self._badge_lbl.setFixedHeight(24)
        self._badge_lbl.setStyleSheet(
            f"background:{state_color}33; color:{state_color};"
            f" border:1px solid {state_color}; border-radius:12px;"
            f" padding:0 10px; font-size:8pt; font-weight:bold;")
        title_row.addWidget(self._title_lbl)
        title_row.addStretch()
        title_row.addWidget(self._badge_lbl)
        root.addLayout(title_row)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{Colors.BORDER};")
        root.addWidget(sep)

        # Diagrama ─────────────────────────────────────────────────────────────
        root.addWidget(QLabel("Diagrama de 5 Estados", styleSheet=(
            f"color:{Colors.TEXT_SEC}; font-size:9pt; font-weight:600;")))
        self._diagram = _StateDiagram()
        root.addWidget(self._diagram)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"color:{Colors.BORDER};")
        root.addWidget(sep2)

        # Campos PCB ───────────────────────────────────────────────────────────
        root.addWidget(QLabel("Campos de la PCB", styleSheet=(
            f"color:{Colors.TEXT_SEC}; font-size:9pt; font-weight:600;")))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        fw = QWidget(); fw.setStyleSheet("background: transparent;")
        fl = QVBoxLayout(fw)
        fl.setSpacing(4); fl.setContentsMargins(0, 0, 0, 0)

        self._val_labels: dict[str, QLabel] = {}
        self._keys_map:   dict[str, tuple]  = {}

        def add(label, *keys, fmt=None, fmt_func=None):
            self._keys_map[label] = (keys, fmt, fmt_func)
            v = None
            for k in keys:
                val = proc.get(k)
                if val is not None:
                    v = val; break
            if v is not None:
                if fmt_func:
                    try: v = fmt_func(v)
                    except Exception: pass
                elif fmt:
                    try: v = fmt.format(v)
                    except Exception: pass
            row_layout, val_lbl = _field_row(label, v)
            self._val_labels[label] = val_lbl
            fl.addLayout(row_layout)

        if proc.get("state") == "TERMINATED" and "finish_time" not in proc:
            arr  = proc.get("arrival_tick", proc.get("arrival_time", 0))
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
        fl.addWidget(_divider())
        add("Program Counter (PC)",  "pc", "program_counter", fmt="0x{:04X}")
        add("PC (hex)",              "pc_hex")
        add("Núcleo Asignado (CPU)", "cpu_id")
        fl.addWidget(_divider())
        add("Mem. Asignada (MB)",    "mem_mb", "memory_size", "memory_mb")
        add("Dir. Base Física",      "memory_base_address", fmt="0x{:04X}")
        add("Dispositivo I/O",       "io_device")
        fl.addWidget(_divider())

        def fmt_regs(r):
            if isinstance(r, dict):
                return " ".join(
                    f"{k}:0x{v:04X}" if isinstance(v, int) else f"{k}:{v}"
                    for k, v in r.items())
            return str(r)

        add("Registros",             "registers", fmt_func=fmt_regs)
        fl.addStretch()
        scroll.setWidget(fw)
        root.addWidget(scroll, 1)

        # Botón cerrar ─────────────────────────────────────────────────────────
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        btn_box.setStyleSheet(
            f"QPushButton {{ background:{Colors.BG_ELEVATED}; color:{Colors.TEXT_PRIMARY};"
            f" border:1px solid {Colors.BORDER}; border-radius:4px; padding:4px 16px; }}"
            f"QPushButton:hover {{ background:{Colors.ACCENT_DARK}; }}"
        )
        root.addWidget(btn_box)

        # Cargar estado inicial — el historial previo se inyectará desde
        # pcb_table vía load_history() justo después de crear el dialog.
        self._diagram.set_state(state_str)

    def load_history(self, states: list[str]) -> None:
        """
        Inyecta el historial de estados que el proceso ya recorrió ANTES de
        que se abriera este inspector. Llamar inmediatamente después de __init__.
        """
        self._diagram.load_history(states)

    def update_data(self, proc: dict) -> None:
        """Actualiza la UI en tiempo real (llamado en cada tick desde pcb_table)."""
        pid  = proc.get('pid', '?')
        name = proc.get('name', '')
        self.setWindowTitle(f"Inspector PCB — P{pid} ({name})")
        self._title_lbl.setText(f"P{pid}  {name}")

        state_str   = str(proc.get("state", "UNKNOWN")).upper()
        state_color = STATE_COLORS.get(state_str, Colors.TEXT_MUTED)
        self._badge_lbl.setText(state_str)
        self._badge_lbl.setStyleSheet(
            f"background:{state_color}33; color:{state_color};"
            f" border:1px solid {state_color}; border-radius:12px;"
            f" padding:0 10px; font-size:8pt; font-weight:bold;")

        # El diagrama maneja internamente si el estado realmente cambió
        self._diagram.set_state(state_str)

        for label, (keys, fmt, fmt_func) in self._keys_map.items():
            v = None
            for k in keys:
                val = proc.get(k)
                if val is not None:
                    v = val; break
            if v is not None:
                if fmt_func:
                    try: v = fmt_func(v)
                    except Exception: pass
                elif fmt:
                    try: v = fmt.format(v)
                    except Exception: pass
            if label in self._val_labels:
                self._val_labels[label].setText(str(v) if v is not None else "—")