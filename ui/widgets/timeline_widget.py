"""
ui/widgets/timeline_widget.py — Widget del Gráfico de Gantt/Timeline.
"""
from __future__ import annotations
from typing import List, Tuple

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QFontMetrics
from PySide6.QtWidgets import QWidget, QScrollArea, QVBoxLayout

from ui.styles import Colors, STATE_COLORS

class TimelineDrawWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.timeline: List[Tuple[int, Optional[int], str, str, str]] = []
        self.num_cores = 1
        self.setMinimumWidth(800)
        self.setMinimumHeight(130)

    def update_timeline(self, timeline: List[Tuple[int, Optional[int], str, str, str]], num_cores: int):
        self.timeline = timeline
        self.num_cores = max(1, num_cores)
        # Calculate width needed
        if self.timeline:
            max_tick = max(t[0] for t in self.timeline)
            min_tick = min(t[0] for t in self.timeline)
            tick_span = max_tick - min_tick
            needed_width = max(800, tick_span * 30 + 100)
            self.setMinimumWidth(needed_width)
            
        # Adjust height based on number of cores
        self.setMinimumHeight(max(130, self.num_cores * 100))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.timeline:
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin eventos en el timeline")
            return

        min_tick = min(t[0] for t in self.timeline)
        max_tick = max(t[0] for t in self.timeline)
        
        width = self.width() - 80
        x_offset = 60
        
        # Draw main axes for each core
        lane_height = self.height() // self.num_cores
        
        for i in range(self.num_cores):
            y_center = (i * lane_height) + (lane_height // 2)
            painter.setPen(QPen(QColor(Colors.BORDER), 2))
            painter.drawLine(x_offset, y_center, x_offset + width, y_center)
            
            # Draw Core Label
            painter.setPen(QColor(Colors.CORE_COLORS[i % len(Colors.CORE_COLORS)]))
            painter.drawText(5, y_center + 4, f"Core {i}")

        if max_tick == min_tick:
            return

        fm = QFontMetrics(self.font())
        for i, (tick, core_id, name, from_s, to_s) in enumerate(self.timeline):
            x = x_offset + int(((tick - min_tick) / (max_tick - min_tick)) * width)
            
            c_id = core_id if core_id is not None else 0
            y_center = (c_id * lane_height) + (lane_height // 2)
            
            # Determine color based on to_state
            base_state = to_s.split("(")[0]
            color_hex = STATE_COLORS.get(base_state, Colors.TEXT_MUTED)
            color = QColor(color_hex)

            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(x - 5, y_center - 5, 10, 10)

            # Stagger text vertically to prevent overlapping
            stagger = i % 3
            y_text = y_center - 15 - (stagger * 15)
            y_state = y_center + 20 + (stagger * 15)

            # Draw text
            painter.setPen(QColor(Colors.TEXT_SEC))
            text = f"{name}"
            tw = fm.horizontalAdvance(text)
            painter.drawText(x - tw//2, y_text, text)
            
            state_text = to_s
            sw = fm.horizontalAdvance(state_text)
            painter.setPen(color)
            painter.drawText(x - sw//2, y_state, state_text)

class TimelineWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {Colors.BG_SURFACE}; }}")
        
        self.draw_widget = TimelineDrawWidget()
        self.scroll.setWidget(self.draw_widget)
        
        layout.addWidget(self.scroll)

    def update(self, timeline: List[Tuple[int, Optional[int], str, str, str]], num_cores: int = 1):
        self.draw_widget.update_timeline(timeline, num_cores)
        # Scroll to right automatically
        hbar = self.scroll.horizontalScrollBar()
        hbar.setValue(hbar.maximum())
