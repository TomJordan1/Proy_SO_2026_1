"""
ui/widgets/gantt_widget.py — Diagrama de Gantt de procesos.
"""
from __future__ import annotations
from typing import List, Dict, Any

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QFontMetrics, QBrush
from PySide6.QtWidgets import QWidget, QScrollArea, QVBoxLayout

from ui.styles import Colors, STATE_COLORS

class GanttDrawWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._timeline = []
        self._current_tick = 0
        self._processes = {}
        self.setMinimumSize(800, 300)

    def update_data(self, timeline: List[Dict[str, Any]], current_tick: int):
        self._timeline = timeline
        self._current_tick = current_tick
        
        # Obtener los pids y nombres
        self._processes = {}
        for event in timeline:
            label = event.get("label", "")
            # Asume label: "P1(ProcName)" o similar
            pid_str = label.split("(")[0].replace("P", "")
            try:
                pid = int(pid_str)
                self._processes[pid] = label
            except:
                pass
                
        # Calcular dimensiones
        max_tick = current_tick
        width = max(800, max_tick * 40 + 150)
        self.setMinimumWidth(width)
        height = max(300, len(self._processes) * 40 + 60)
        self.setMinimumHeight(height)
        
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._timeline:
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos para el diagrama de Gantt")
            return

        fm = QFontMetrics(self.font())
        row_height = 40
        margin_left = 100
        margin_top = 40
        tick_width = 30
        max_tick = self._current_tick
        
        painter.fillRect(self.rect(), QColor(Colors.BG_SURFACE))

        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        for tick in range(max_tick + 1):
            x = margin_left + tick * tick_width
            painter.drawLine(x, margin_top - 10, x, self.height())
            if tick % 5 == 0 or tick == max_tick:
                painter.setPen(QColor(Colors.TEXT_MUTED))
                painter.drawText(x - 10, margin_top - 15, str(tick))
                painter.setPen(QPen(QColor(Colors.BORDER), 1))

        sorted_pids = sorted(self._processes.keys())
        for i, pid in enumerate(sorted_pids):
            label = self._processes[pid]
            y_center = margin_top + i * row_height + row_height // 2
            
            painter.setPen(QColor(Colors.TEXT_PRIMARY))
            painter.drawText(5, y_center + 4, label)
            
            painter.setPen(QPen(QColor(Colors.BORDER), 1))
            painter.drawLine(margin_left, y_center, margin_left + max_tick * tick_width, y_center)
            
            # Reconstruir los rangos de estados para este proceso desde su historial de transiciones
            process_events = [e for e in self._timeline if e.get("label") == label and e.get("tick", 0) <= max_tick]
            if not process_events:
                continue
                
            # Asumir que empieza en NEW en t=0 o en el primer evento
            curr_state = "NEW"
            start_tick = 0
            
            def draw_block(s_tick, e_tick, state):
                if state in ["UNKNOWN", "NEW", "TERMINATED"]:
                    return
                x_start = margin_left + s_tick * tick_width
                block_w = (e_tick - s_tick) * tick_width
                if block_w <= 0:
                    block_w = tick_width  # al menos 1 tick visualmente
                color_hex = STATE_COLORS.get(state, Colors.TEXT_MUTED)
                color = QColor(color_hex)
                rect_y = y_center - 10
                rect_h = 20
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawRoundedRect(x_start, rect_y, block_w, rect_h, 4, 4)
                if block_w > 20:
                    painter.setPen(QColor("#FFFFFF"))
                    painter.drawText(x_start, rect_y, block_w, rect_h, Qt.AlignCenter, state[0])

            # Recorremos eventos para dibujar el bloque anterior
            for ev in process_events:
                ev_tick = ev.get("tick", 0)
                if ev_tick > start_tick:
                    draw_block(start_tick, ev_tick, curr_state)
                curr_state = ev.get("to_state", "")
                start_tick = ev_tick
                
            # Dibujar hasta el current_tick actual
            if start_tick < max_tick and curr_state != "TERMINATED":
                draw_block(start_tick, max_tick + 1, curr_state)


class GanttWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {Colors.BG_SURFACE}; }}")
        
        self.draw_widget = GanttDrawWidget()
        self.scroll.setWidget(self.draw_widget)
        
        layout.addWidget(self.scroll)

    def update_gantt(self, timeline: List[Dict[str, Any]], current_tick: int):
        hbar = self.scroll.horizontalScrollBar()
        is_at_end = hbar.value() >= hbar.maximum() - 10

        self.draw_widget.update_data(timeline, current_tick)
        
        if is_at_end:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: hbar.setValue(hbar.maximum()))
