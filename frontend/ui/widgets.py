"""
ui/widgets.py — Widgets personalizados de la interfaz de PatatOS.

Contiene todos los widgets reutilizables que se usan en main_window.py:

  ┌──────────────────┬────────────────────────────────────────────────────┐
  │ Widget           │ Descripción                                        │
  ├──────────────────┼────────────────────────────────────────────────────┤
  │ CPUWidget        │ Panel que muestra el proceso en CPU                │
  │ MemoryWidget     │ Mapa visual de la memoria (bloques coloreados)     │
  │ QueueWidget      │ Cola de procesos (READY o WAITING) como tarjetas   │
  │ PCBTableWidget   │ Tabla completa de todos los procesos               │
  │ LogWidget        │ Log del sistema con colores por tipo de mensaje     │
  │ MetricsWidget    │ Panel de métricas (CPU util, throughput, etc.)     │
  │ IOStatusWidget   │ Estado de los dispositivos I/O                     │
  └──────────────────┴────────────────────────────────────────────────────┘

Principio de diseño:
  - Cada widget recibe datos puros (no el engine) → fácil de actualizar
  - El main_window es el responsable de conectar el engine con los widgets
  - Los widgets son "tontos" (dumb widgets): solo muestran, no lógica de SO
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QRect
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush, QFontMetrics, QLinearGradient
)
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QPlainTextEdit,
    QFrame, QScrollArea, QSizePolicy, QProgressBar, QGroupBox,
    QSplitter
)

from .styles import Colors, state_color, state_bg_color, process_color_by_pid


# ─────────────────────────────────────────────────────────────────────────────
# Helper: crear label estilizado
# ─────────────────────────────────────────────────────────────────────────────

def make_label(
    text: str,
    color: str = Colors.TEXT_PRI,
    bold: bool = False,
    size: int = 10,
    align=Qt.AlignmentFlag.AlignLeft
) -> QLabel:
    """Crea un QLabel con estilo predefinido."""
    lbl = QLabel(text)
    lbl.setAlignment(align)
    font = QFont()
    font.setPointSize(size)
    font.setBold(bold)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color}; background: transparent; border: none;")
    return lbl


# ─────────────────────────────────────────────────────────────────────────────
# CPUWidget — Panel del proceso en CPU
# ─────────────────────────────────────────────────────────────────────────────

class CPUWidget(QGroupBox):
    """
    Muestra el estado actual de la CPU:
      - Proceso en ejecución (o "IDLE")
      - Progreso del burst_time
      - Quantum restante (en Round Robin)
      - Tick actual
    """

    def __init__(self, parent=None):
        super().__init__("🖥  CPU", parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Nombre del proceso y estado
        self.lbl_process = make_label(
            "IDLE", color=Colors.TEXT_MUTED, bold=True, size=14,
            align=Qt.AlignmentFlag.AlignCenter
        )
        self.lbl_pid = make_label(
            "PID: --", color=Colors.TEXT_SEC, size=9,
            align=Qt.AlignmentFlag.AlignCenter
        )

        # Barra de progreso del burst_time
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background: {Colors.BG_SURFACE};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background: {Colors.STATE_RUNNING};
                border-radius: 4px;
            }}
        """)

        # Grid de métricas del proceso actual
        grid = QGridLayout()
        grid.setSpacing(4)

        self.lbl_burst     = make_label("--", Colors.TEXT_PRI, bold=True)
        self.lbl_remaining = make_label("--", Colors.STATE_RUNNING, bold=True)
        self.lbl_quantum   = make_label("--", Colors.STATE_WAITING, bold=True)
        self.lbl_pc        = make_label("--", Colors.TEXT_SEC)
        self.lbl_priority  = make_label("--", Colors.TEXT_PRI)
        self.lbl_tick      = make_label("T=0", Colors.ACCENT_LIGHT, bold=True,
                                        size=12, align=Qt.AlignmentFlag.AlignCenter)

        grid.addWidget(make_label("Burst:", Colors.TEXT_SEC), 0, 0)
        grid.addWidget(self.lbl_burst, 0, 1)
        grid.addWidget(make_label("Restante:", Colors.TEXT_SEC), 1, 0)
        grid.addWidget(self.lbl_remaining, 1, 1)
        grid.addWidget(make_label("Quantum:", Colors.TEXT_SEC), 2, 0)
        grid.addWidget(self.lbl_quantum, 2, 1)
        grid.addWidget(make_label("PC:", Colors.TEXT_SEC), 3, 0)
        grid.addWidget(self.lbl_pc, 3, 1)
        grid.addWidget(make_label("Prioridad:", Colors.TEXT_SEC), 4, 0)
        grid.addWidget(self.lbl_priority, 4, 1)

        layout.addWidget(self.lbl_tick)
        layout.addWidget(self.lbl_process)
        layout.addWidget(self.lbl_pid)
        layout.addWidget(self.progress)
        layout.addLayout(grid)
        layout.addStretch()

    def update_cpu(
        self,
        process_name: Optional[str],
        pid: Optional[int],
        burst_time: int,
        remaining_time: int,
        quantum_remaining: int,
        program_counter: int,
        priority: int,
        current_tick: int,
    ):
        """Actualiza todos los datos del panel CPU."""
        self.lbl_tick.setText(f"T = {current_tick}")

        if process_name is None:
            # CPU idle
            self.lbl_process.setText("─── IDLE ───")
            self.lbl_process.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; background: transparent; "
                f"border: none; font-size: 14pt; font-weight: bold;"
            )
            self.lbl_pid.setText("PID: --")
            self.progress.setValue(0)
            self.lbl_burst.setText("--")
            self.lbl_remaining.setText("--")
            self.lbl_quantum.setText("--")
            self.lbl_pc.setText("--")
            self.lbl_priority.setText("--")
        else:
            self.lbl_process.setText(f"▶  {process_name}")
            self.lbl_process.setStyleSheet(
                f"color: {Colors.STATE_RUNNING}; background: transparent; "
                f"border: none; font-size: 13pt; font-weight: bold;"
            )
            self.lbl_pid.setText(f"PID: {pid}")
            pct = int((1 - remaining_time / max(1, burst_time)) * 100)
            self.progress.setValue(pct)
            self.lbl_burst.setText(str(burst_time))
            self.lbl_remaining.setText(str(remaining_time))
            q_text = str(quantum_remaining) if quantum_remaining > 0 else "N/A"
            self.lbl_quantum.setText(q_text)
            self.lbl_pc.setText(f"0x{program_counter:04X}")
            self.lbl_priority.setText(str(priority))


# ─────────────────────────────────────────────────────────────────────────────
# MemoryWidget — Mapa visual de la memoria
# ─────────────────────────────────────────────────────────────────────────────

class MemoryWidget(QWidget):
    """
    Mapa visual de la memoria física simulada.

    Dibuja una cuadrícula donde cada celda es un bloque de memoria:
      - Gris oscuro: libre
      - Gris medio: reservado para el SO (kernel)
      - Color por PID: proceso de usuario

    Usa QPainter para dibujar directamente en el widget (más eficiente
    que crear un QLabel por bloque cuando hay 32+ bloques).
    """

    CELL_SIZE    = 38   # Píxeles por bloque
    CELL_PADDING = 2    # Espaciado entre bloques
    COLS         = 8    # Bloques por fila

    def __init__(self, total_blocks: int = 32, block_size_mb: int = 32, parent=None):
        super().__init__(parent)
        self.total_blocks = total_blocks
        self.block_size_mb = block_size_mb
        self._snapshot: List[Optional[int]] = [None] * total_blocks

        # Calcular tamaño necesario
        rows = (total_blocks + self.COLS - 1) // self.COLS
        w = self.COLS * (self.CELL_SIZE + self.CELL_PADDING) + self.CELL_PADDING
        h = rows * (self.CELL_SIZE + self.CELL_PADDING) + self.CELL_PADDING
        self.setMinimumSize(w, h)
        self.setMaximumHeight(h + 10)

    def update_memory(self, snapshot: List[Optional[int]]) -> None:
        """
        Actualiza el mapa de memoria y redibuja el widget.

        Args:
            snapshot: Lista de PIDs por bloque (None=libre, 0=SO, N=proceso)
        """
        self._snapshot = snapshot
        self.update()  # Solicitar redibujo a Qt

    def paintEvent(self, event):
        """
        Dibuja el mapa de memoria con QPainter.

        Se llama automáticamente por Qt cuando el widget necesita redibujarse.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cell = self.CELL_SIZE
        pad  = self.CELL_PADDING

        for i, owner in enumerate(self._snapshot):
            col = i % self.COLS
            row = i // self.COLS

            x = pad + col * (cell + pad)
            y = pad + row * (cell + pad)

            # ── Color de fondo del bloque ─────────────────────────────────────
            if owner is None:
                # Bloque libre
                bg = QColor(Colors.MEMORY_FREE)
                text_color = QColor(Colors.TEXT_MUTED)
                label = "FREE"
            elif owner == 0:
                # Reservado para el SO
                bg = QColor(Colors.MEMORY_OS)
                text_color = QColor(Colors.TEXT_SEC)
                label = "SO"
            else:
                # Proceso de usuario
                bg = QColor(process_color_by_pid(owner))
                text_color = QColor("#ffffff")
                label = f"P{owner}"

            # Dibujar fondo del bloque con bordes redondeados
            painter.setBrush(QBrush(bg))
            painter.setPen(QPen(QColor(Colors.BORDER), 1))
            painter.drawRoundedRect(x, y, cell, cell, 5, 5)

            # Dibujar etiqueta centrada
            painter.setPen(QPen(text_color))
            font = QFont("Segoe UI", 7)
            font.setBold(owner is not None and owner > 0)
            painter.setFont(font)
            painter.drawText(
                x, y, cell, cell,
                Qt.AlignmentFlag.AlignCenter,
                label
            )

            # Dibujar número de bloque en esquina superior izquierda
            painter.setPen(QPen(QColor(Colors.TEXT_MUTED)))
            small_font = QFont("Segoe UI", 6)
            painter.setFont(small_font)
            painter.drawText(x + 3, y + 9, str(i))

        painter.end()


# ─────────────────────────────────────────────────────────────────────────────
# QueueWidget — Cola de procesos (READY o WAITING)
# ─────────────────────────────────────────────────────────────────────────────

class ProcessChip(QFrame):
    """
    Tarjeta pequeña que representa un proceso en una cola.

    Muestra: nombre, PID, estado y un indicador de color.
    """

    def __init__(self, name: str, pid: int, state: str, extra: str = "", parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self.setMinimumWidth(80)
        self.setMaximumWidth(110)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        color = state_color(state)
        bg = state_bg_color(state)

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {color};
                border-radius: 6px;
                border-left: 3px solid {color};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        lbl_name = QLabel(name[:12])
        lbl_name.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 9pt; border:none; background:transparent;")
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_pid = QLabel(f"PID {pid}")
        lbl_pid.setStyleSheet(f"color: {Colors.TEXT_SEC}; font-size: 8pt; border:none; background:transparent;")
        lbl_pid.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if extra:
            lbl_extra = QLabel(extra)
            lbl_extra.setStyleSheet(f"color: {Colors.TEXT_SEC}; font-size: 7pt; border:none; background:transparent;")
            lbl_extra.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl_extra)

        layout.addWidget(lbl_name)
        layout.addWidget(lbl_pid)


class QueueWidget(QGroupBox):
    """
    Muestra una cola de procesos (READY o WAITING) como chips horizontales.

    Scroll horizontal cuando hay muchos procesos.
    """

    def __init__(self, title: str, state: str, parent=None):
        super().__init__(title, parent)
        self.state = state
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 8)

        # Contador de procesos en la cola
        self.lbl_count = make_label("0 procesos", Colors.TEXT_SEC, size=8)
        layout.addWidget(self.lbl_count)

        # Área scrollable horizontal
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFixedHeight(80)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        # Contenedor de chips
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.chips_layout = QHBoxLayout(self.container)
        self.chips_layout.setSpacing(6)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def update_queue(self, processes: list) -> None:
        """
        Actualiza la vista de la cola con la lista de procesos.

        Args:
            processes: Lista de PCBs en la cola
        """
        # Limpiar chips anteriores
        while self.chips_layout.count():
            item = self.chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        count = len(processes)
        self.lbl_count.setText(
            f"{count} proceso{'s' if count != 1 else ''}"
        )

        if count == 0:
            placeholder = make_label("─── vacío ───", Colors.TEXT_MUTED, size=9,
                                     align=Qt.AlignmentFlag.AlignCenter)
            self.chips_layout.addWidget(placeholder)
            return

        for pcb in processes:
            extra = ""
            if self.state == "WAITING" and hasattr(pcb, 'io_device') and pcb.io_device:
                extra = f"⏳ {pcb.io_device}"
                if hasattr(pcb, 'io_remaining') and pcb.io_remaining > 0:
                    extra += f" {pcb.io_remaining}t"
            chip = ProcessChip(pcb.name, pcb.pid, pcb.state, extra)
            self.chips_layout.addWidget(chip)

        self.chips_layout.addStretch()


# ─────────────────────────────────────────────────────────────────────────────
# PCBTableWidget — Tabla de todos los procesos
# ─────────────────────────────────────────────────────────────────────────────

class PCBTableWidget(QTableWidget):
    """
    Tabla que muestra el PCB completo de todos los procesos.

    Columnas:
      PID | Nombre | Estado | Burst | Restante | PC | Prioridad |
      Mem | Espera | Respuesta | I/O Device
    """

    COLUMNS = [
        "PID", "Nombre", "Estado", "Burst", "Restante", "%",
        "PC", "Prior.", "Mem(B)", "T.Espera", "T.Resp.", "Disp. I/O"
    ]

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self._setup_table()

    def _setup_table(self):
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setStyleSheet(self.styleSheet() + f"""
            QTableWidget {{
                alternate-background-color: {Colors.BG_SURFACE};
            }}
        """)

    def update_table(self, processes: list) -> None:
        """Actualiza la tabla con la lista completa de procesos."""
        # No disparar signals mientras actualizamos (performance)
        self.setSortingEnabled(False)
        self.setRowCount(len(processes))

        for row, pcb in enumerate(processes):
            state = str(pcb.state) if hasattr(pcb.state, '__str__') else pcb.state
            color = state_color(state)

            values = [
                str(pcb.pid),
                pcb.name,
                state,
                str(pcb.burst_time),
                str(pcb.remaining_time),
                f"{pcb.completion_percent:.0f}%",
                f"0x{pcb.program_counter:04X}",
                str(pcb.priority),
                f"{pcb.memory_address}" if pcb.memory_address >= 0 else "--",
                str(pcb.waiting_time),
                str(pcb.response_time),
                pcb.io_device or "--",
            ]

            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Colorear la columna de estado
                if col == 2:
                    item.setForeground(QColor(color))

                self.setItem(row, col, item)

        self.setSortingEnabled(True)


# ─────────────────────────────────────────────────────────────────────────────
# LogWidget — Log del sistema con colores
# ─────────────────────────────────────────────────────────────────────────────

class LogWidget(QGroupBox):
    """
    Panel de log del sistema con mensajes coloreados por tipo.

    Colores:
      - Mensajes de proceso nuevo: azul
      - RUNNING: violeta
      - WAITING: ámbar
      - TERMINATED/OK: verde
      - ERROR: rojo
      - I/O: cyan
      - TIMER/interrupción: amarillo
    """

    MAX_LINES = 300  # Máximo de líneas en el log

    def __init__(self, parent=None):
        super().__init__("📋  Log del Sistema", parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 8)
        layout.setSpacing(4)

        # Controles del log
        ctrl_layout = QHBoxLayout()
        self.btn_clear = make_label("")
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # Área de texto del log
        self.text_area = QPlainTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setMaximumBlockCount(self.MAX_LINES)
        layout.addWidget(self.text_area)

    def append_messages(self, messages: List[str]) -> None:
        """
        Agrega mensajes al log con colores según el contenido.

        Llamar con los nuevos mensajes (no todos los mensajes).
        """
        cursor = self.text_area.textCursor()
        from PySide6.QtGui import QTextCharFormat

        for msg in messages:
            # Determinar color por contenido del mensaje
            html_color = self._get_color_for_message(msg)
            self.text_area.appendHtml(
                f'<span style="color:{html_color}; font-family: Consolas, monospace;">'
                f'{msg}</span>'
            )

        # Auto-scroll al final
        scrollbar = self.text_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _get_color_for_message(self, msg: str) -> str:
        """Determina el color HTML de un mensaje según su contenido."""
        msg_upper = msg.upper()
        if "ERROR" in msg_upper or "❌" in msg:
            return Colors.ERROR
        if "TERMINADO" in msg_upper or "OK ✓" in msg:
            return Colors.SUCCESS
        if "WAITING" in msg_upper or "WAITING" in msg_upper or "🔄" in msg:
            return Colors.STATE_WAITING
        if "RUNNING" in msg_upper or "▶" in msg:
            return Colors.STATE_RUNNING
        if "READY" in msg_upper or "ADMITIDO" in msg_upper:
            return Colors.STATE_READY
        if "TIMER" in msg_upper or "⚡" in msg:
            return Colors.WARNING
        if "🆕" in msg or "CREADO" in msg_upper:
            return Colors.STATE_NEW
        if "RESET" in msg_upper or "🔄" in msg:
            return Colors.INFO
        return Colors.TEXT_SEC

    def clear_log(self) -> None:
        """Limpia el log."""
        self.text_area.clear()


# ─────────────────────────────────────────────────────────────────────────────
# MetricsWidget — Panel de métricas de rendimiento
# ─────────────────────────────────────────────────────────────────────────────

class MetricCard(QFrame):
    """Tarjeta individual de una métrica con valor grande y descripción."""

    def __init__(self, title: str, unit: str = "", color: str = Colors.ACCENT_LIGHT, parent=None):
        super().__init__(parent)
        self.unit = unit
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                border-top: 3px solid {color};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self.lbl_title = make_label(title, Colors.TEXT_SEC, size=8)
        self.lbl_value = make_label("--", color, bold=True, size=18,
                                    align=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)

    def set_value(self, value: str) -> None:
        """Actualiza el valor mostrado."""
        self.lbl_value.setText(f"{value}{self.unit}")


class MetricsWidget(QGroupBox):
    """
    Panel con tarjetas de métricas de rendimiento.

    Métricas mostradas:
      - CPU Utilization (%)
      - Throughput (proc/tick)
      - Avg Waiting Time (ticks)
      - Avg Response Time (ticks)
    """

    def __init__(self, parent=None):
        super().__init__("📊  Métricas", parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 16, 8, 8)

        self.card_cpu = MetricCard("CPU Utilización", "%", Colors.STATE_RUNNING)
        self.card_throughput = MetricCard("Throughput", "/tick", Colors.STATE_READY)
        self.card_waiting = MetricCard("Espera Prom.", "t", Colors.STATE_WAITING)
        self.card_response = MetricCard("Respuesta Prom.", "t", Colors.STATE_NEW)
        self.card_completed = MetricCard("Completados", "", Colors.SUCCESS)
        self.card_errors = MetricCard("Errores", "", Colors.ERROR)

        layout.addWidget(self.card_cpu,        0, 0)
        layout.addWidget(self.card_throughput,  0, 1)
        layout.addWidget(self.card_waiting,     1, 0)
        layout.addWidget(self.card_response,    1, 1)
        layout.addWidget(self.card_completed,   2, 0)
        layout.addWidget(self.card_errors,      2, 1)

    def update_metrics(self, metrics: Dict[str, Any]) -> None:
        """Actualiza todas las tarjetas de métricas."""
        self.card_cpu.set_value(str(metrics.get("cpu_utilization", 0.0)))
        self.card_throughput.set_value(str(metrics.get("throughput", 0.0)))
        self.card_waiting.set_value(str(metrics.get("avg_waiting_time", 0.0)))
        self.card_response.set_value(str(metrics.get("avg_response_time", 0.0)))
        self.card_completed.set_value(str(metrics.get("total_completed", 0)))
        self.card_errors.set_value(str(metrics.get("total_errors", 0)))


# ─────────────────────────────────────────────────────────────────────────────
# IOStatusWidget — Estado de dispositivos I/O
# ─────────────────────────────────────────────────────────────────────────────

class DeviceRow(QFrame):
    """Fila que muestra el estado de un dispositivo I/O."""

    def __init__(self, name: str, icon: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # Ícono del dispositivo
        self.lbl_icon = make_label(f"{icon} {name}", Colors.TEXT_PRI, bold=True)
        self.lbl_icon.setFixedWidth(110)

        # Indicador de estado (LED)
        self.lbl_status = make_label("●  LIBRE", Colors.DEVICE_FREE, bold=True)
        self.lbl_status.setFixedWidth(80)

        # Proceso actual
        self.lbl_current = make_label("--", Colors.TEXT_SEC)

        # Cola
        self.lbl_queue = make_label("Q:0", Colors.TEXT_SEC, size=9)
        self.lbl_queue.setFixedWidth(35)

        # Total atendidos
        self.lbl_served = make_label("0 atendidos", Colors.TEXT_MUTED, size=8)
        self.lbl_served.setFixedWidth(80)

        layout.addWidget(self.lbl_icon)
        layout.addWidget(self.lbl_status)
        layout.addWidget(self.lbl_current)
        layout.addStretch()
        layout.addWidget(self.lbl_queue)
        layout.addWidget(self.lbl_served)

    def update_status(self, busy: bool, current: str, queue_len: int, served: int, ticks_rem: int):
        """Actualiza el estado visual del dispositivo."""
        if busy:
            self.lbl_status.setText(f"● OCUPADO")
            self.lbl_status.setStyleSheet(
                f"color: {Colors.DEVICE_BUSY}; font-weight: bold; background: transparent; border: none;"
            )
            self.lbl_current.setText(f"{current} ({ticks_rem}t)")
        else:
            self.lbl_status.setText("●  LIBRE")
            self.lbl_status.setStyleSheet(
                f"color: {Colors.DEVICE_FREE}; font-weight: bold; background: transparent; border: none;"
            )
            self.lbl_current.setText("--")

        self.lbl_queue.setText(f"Q:{queue_len}")
        self.lbl_served.setText(f"{served} atendidos")


class IOStatusWidget(QGroupBox):
    """Panel que muestra el estado de todos los dispositivos I/O."""

    def __init__(self, parent=None):
        super().__init__("⚙  Dispositivos I/O", parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 8)
        layout.setSpacing(6)

        self._rows: Dict[str, DeviceRow] = {}

        device_defs = [
            ("KEYBOARD", "⌨"),
            ("DISK",     "💾"),
            ("PRINTER",  "🖨"),
        ]

        for name, icon in device_defs:
            row = DeviceRow(name, icon)
            self._rows[name] = row
            layout.addWidget(row)

        layout.addStretch()

    def update_devices(self, status_list: List[Dict]) -> None:
        """Actualiza el estado de todos los dispositivos."""
        for dev_status in status_list:
            name = dev_status["name"]
            row = self._rows.get(name)
            if row:
                row.update_status(
                    busy=dev_status["busy"],
                    current=dev_status["current"],
                    queue_len=dev_status["queue_length"],
                    served=dev_status["total_served"],
                    ticks_rem=dev_status["ticks_rem"],
                )
