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

    def update_timeline(self, timeline, num_cores: int):
        # Normalise: accept list-of-dicts or list-of-tuples
        normalised = []
        for entry in timeline:
            if isinstance(entry, dict):
                normalised.append((
                    entry.get("tick", 0),
                    entry.get("core_id"),
                    entry.get("label", ""),
                    entry.get("from_state", ""),
                    entry.get("to_state", ""),
                ))
            else:
                normalised.append(tuple(entry))
        self.timeline = normalised
        self.num_cores = max(1, num_cores)
        # Calcular el ancho necesario
        if self.timeline:
            max_tick = max(t[0] for t in self.timeline)
            min_tick = min(t[0] for t in self.timeline)
            tick_span = max_tick - min_tick
            needed_width = max(800, tick_span * 40 + 100)
            self.setMinimumWidth(needed_width)
            
        # Ajusta la altura según el número de núcleos, deja suficiente espacio para el texto
        self.setMinimumHeight(max(180, self.num_cores * 160))
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
        
        # Dibuja los ejes principales de cada núcleo
        lane_height = self.height() // self.num_cores
        
        for i in range(self.num_cores):
            y_center = (i * lane_height) + (lane_height // 2)
            painter.setPen(QPen(QColor(Colors.BORDER), 2))
            painter.drawLine(x_offset, y_center, x_offset + width, y_center)
            
            # Dibujar etiqueta del núcleo
            painter.setPen(QColor(Colors.CORE_COLORS[i % len(Colors.CORE_COLORS)]))
            painter.drawText(5, y_center + 4, f"Core {i}")

        if max_tick == min_tick:
            return

        fm = QFontMetrics(self.font())

        # Agrupar eventos que están muy cerca visualmente
        from collections import defaultdict
        groups_per_core = defaultdict(list)
        
        for entry in self.timeline:
            tick, core_id, name, from_s, to_s = entry
            c_id = core_id if core_id is not None else 0
            x = x_offset + int(((tick - min_tick) / (max_tick - min_tick)) * width)
            
            core_groups = groups_per_core[c_id]
            if not core_groups:
                core_groups.append({"x": x, "events": [entry]})
            else:
                last_group = core_groups[-1]
                # Si está a menos de 45 px, se superpondría el texto horizontalmente
                if x - last_group["x"] < 45:
                    last_group["events"].append(entry)
                else:
                    core_groups.append({"x": x, "events": [entry]})

        # Dibujar los grupos
        for c_id, core_groups in groups_per_core.items():
            y_center = (c_id * lane_height) + (lane_height // 2)
            
            # Alternar ligeramente arriba y abajo para grupos contiguos si es necesario, 
            # pero con 45px rara vez chocan, así que podemos mantenerlo simple.
            for idx, grp in enumerate(core_groups):
                x = grp["x"]
                events = grp["events"]
                
                # Pequeño stagger solo de 2 niveles por si los textos son muy largos
                stagger = idx % 2
                y_text = y_center - 15 - (stagger * 12)
                y_state = y_center + 20 + (stagger * 12)
                
                if len(events) == 1:
                    tick, core_id, name, from_s, to_s = events[0]
                    base_state = to_s.split("(")[0]
                    color_hex = STATE_COLORS.get(base_state, Colors.TEXT_MUTED)
                    color = QColor(color_hex)
                    
                    painter.setBrush(color)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(x - 5, y_center - 5, 10, 10)
                    
                    painter.setPen(QColor(Colors.TEXT_SEC))
                    tw = fm.horizontalAdvance(name)
                    painter.drawText(x - tw//2, y_text, name)
                    
                    painter.setPen(color)
                    sw = fm.horizontalAdvance(to_s)
                    painter.drawText(x - sw//2, y_state, to_s)
                else:
                    # Dibujar nodo colapsado
                    painter.setBrush(QColor(Colors.TEXT_MUTED))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(x - 6, y_center - 6, 12, 12)
                    
                    states = [e[4].split("(")[0] for e in events]
                    most_common_state = max(set(states), key=states.count)
                    
                    label_top = f"+{len(events)} proc"
                    label_bot = f"{most_common_state}"
                    
                    painter.setPen(QColor(Colors.TEXT_SEC))
                    tw = fm.horizontalAdvance(label_top)
                    painter.drawText(x - tw//2, y_text, label_top)
                    
                    painter.setPen(QColor(STATE_COLORS.get(most_common_state, Colors.TEXT_MUTED)))
                    sw = fm.horizontalAdvance(label_bot)
                    painter.drawText(x - sw//2, y_state, label_bot)

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
        # Desplazarse automáticamente hacia la derecha
        hbar = self.scroll.horizontalScrollBar()
        hbar.setValue(hbar.maximum())
