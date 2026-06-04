"""
ui/main_window.py — Ventana Principal de PatatOS v2.

Organización del layout:
  ┌─ toolbar ────────────────────────────────────────────────────────────────┐
  │ [▶][⏸][↺]  Algoritmo: [FCFS▼] Q:[4]  Velocidad:[Normal▼]  Mem:[FF▼]   │
  ├─────────────────────────────────────────────────────────────────────────┤
  │         │  Colas READY (una por core)                                   │
  │ CPU     │  ─────────────────────────────────────────────────────────    │
  │ Cores   │  Cola WAITING                                                 │
  │         │  ─────────────────────────────────────────────────────────    │
  ├─────────┤  Tabla PCB (todos los procesos)            │ Métricas         │
  │ Memoria │                                            │                  │
  │ (lineal)│                                            │ I/O Devices      │
  ├─────────┴────────────────────────────────────────────┴──────────────────┤
  │  Timeline (Gantt)                                                        │
  ├──────────────────────────────────────────────────────────────────────────┤
  │  Log del sistema                                                          │
  └──────────────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox,
    QSplitter, QFrame, QToolBar, QDialog, QMessageBox,
    QLineEdit, QDoubleSpinBox, QScrollArea, QMenuBar,
)
from PySide6.QtGui import QAction

from simulation.engine import SimulationEngine, build_scheduler
from simulation.clock import SimClock
from simulation.config import HardwareConfig
from ui.styles import Colors, get_main_stylesheet

# Widgets
from ui.widgets.cpu_widget import CPUWidget
from ui.widgets.memory_widget import MemoryWidget
from ui.widgets.queue_widget import QueueWidget
from ui.widgets.pcb_table import PCBTableWidget
from ui.widgets.metrics_widget import MetricsWidget
from ui.widgets.io_widget import IOStatusWidget
from ui.widgets.timeline_widget import TimelineWidget
from ui.widgets.log_widget import LogWidget


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet(f"color:{Colors.BORDER}; background:{Colors.BORDER};")
    f.setFixedWidth(1)
    return f


def _lbl(text: str, color: str = Colors.TEXT_SEC) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(f"color:{color}; background:transparent; padding:0 4px;")
    return l


class MainWindow(QMainWindow):
    """
    Ventana principal de PatatOS.
    Conecta el SimClock → SimulationEngine → widgets de UI.
    La UI solo lee estado; nunca escribe directamente en el engine.
    """

    def __init__(
        self,
        engine: SimulationEngine,
        clock: SimClock,
        parent=None,
    ):
        super().__init__(parent)
        self.engine = engine
        self.clock = clock
        self._log_offset: int = 0

        self.setWindowTitle("🥔  PatatOS — Simulador de Sistema Operativo")
        self.setMinimumSize(1380, 800)
        self.resize(1600, 900)
        self.setStyleSheet(get_main_stylesheet())

        self._build_toolbar()
        self._build_central()
        self._build_menu()
        self._build_statusbar()

        # Conectar el clock
        self.clock.tick_fired.connect(self._on_tick)

        self._refresh()

    # ─────────────────────────────────────────────────────────────────────────
    # Construcción
    # ─────────────────────────────────────────────────────────────────────────

    def _build_menu(self):
        menu = self.menuBar()
        menu.setStyleSheet(f"QMenuBar {{ background: {Colors.BG_BASE}; color: {Colors.TEXT_PRIMARY}; border-bottom: 1px solid {Colors.BORDER}; }} QMenuBar::item:selected {{ background: {Colors.BG_ELEVATED}; }} QMenu {{ background: {Colors.BG_SURFACE}; color: {Colors.TEXT_PRIMARY}; border: 1px solid {Colors.BORDER}; }}")
        view_menu = menu.addMenu("Ver")

        self._add_toggle_action(view_menu, "Cores de CPU", self.cpu_widget)
        self._add_toggle_action(view_menu, "Mapa de Memoria", self.memory_widget)
        self._add_toggle_action(view_menu, "Colas de Procesos", self.queue_widget)
        self._add_toggle_action(view_menu, "Inspector PCB", self.pcb_table)
        self._add_toggle_action(view_menu, "Dispositivos I/O", self.io_widget)
        self._add_toggle_action(view_menu, "Métricas", self.metrics_widget)
        self._add_toggle_action(view_menu, "Línea de Tiempo", self.timeline_widget)
        self._add_toggle_action(view_menu, "Log del Sistema", self.log_widget)

    def _add_toggle_action(self, menu, name, widget):
        action = QAction(name, self)
        action.setCheckable(True)
        action.setChecked(True)
        action.toggled.connect(widget.setVisible)
        menu.addAction(action)

    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setStyleSheet(f"""
            QToolBar {{
                background:{Colors.BG_BASE};
                border-bottom:1px solid {Colors.BORDER};
                padding:4px 8px; spacing:4px;
            }}
        """)
        self.addToolBar(tb)

        # Logo
        logo = QLabel("🥔  PatatOS")
        logo.setStyleSheet(
            f"color:{Colors.ACCENT_LIGHT}; font-size:13pt; font-weight:bold;"
            f" padding:0 12px 0 4px; background:transparent;"
        )
        tb.addWidget(logo)
        tb.addWidget(_sep())

        # Controles de simulación
        self.btn_start = QPushButton("▶  Iniciar")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.setFixedHeight(30)
        self.btn_start.clicked.connect(self._on_start)
        tb.addWidget(self.btn_start)

        self.btn_pause = QPushButton("⏸  Pausar")
        self.btn_pause.setObjectName("btn_pause")
        self.btn_pause.setFixedHeight(30)
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._on_pause)
        tb.addWidget(self.btn_pause)

        self.btn_reset = QPushButton("↺  Reset")
        self.btn_reset.setObjectName("btn_reset")
        self.btn_reset.setFixedHeight(30)
        self.btn_reset.clicked.connect(self._on_reset)
        tb.addWidget(self.btn_reset)

        tb.addWidget(_sep())

        # Nuevo proceso
        self.btn_new = QPushButton("＋  Nuevo Proceso")
        self.btn_new.setFixedHeight(30)
        self.btn_new.clicked.connect(self._on_new_process)
        tb.addWidget(self.btn_new)

        tb.addWidget(_sep())

        # Scheduler por core (simplificado: core 0)
        tb.addWidget(_lbl("  CPU0:"))
        self.combo_sched = QComboBox()
        self.combo_sched.addItems(["FCFS", "SJF", "SRTF", "Priority", "RR", "MLFQ"])
        self.combo_sched.setFixedWidth(110)
        self.combo_sched.setCurrentText(self.engine.config.scheduler_algorithm)
        self.combo_sched.currentTextChanged.connect(
            lambda name: self.engine.change_scheduler(0, name)
        )
        tb.addWidget(self.combo_sched)

        tb.addWidget(_lbl("Q:"))
        self.spin_q = QSpinBox()
        self.spin_q.setRange(1, 50)
        self.spin_q.setValue(self.engine.config.quantum_default)
        self.spin_q.setFixedWidth(80)
        self.spin_q.valueChanged.connect(
            lambda v: self.engine.change_quantum(0, v)
        )
        tb.addWidget(self.spin_q)

        tb.addWidget(_sep())

        # Velocidad
        tb.addWidget(_lbl("  Vel:"))
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["🐌 Lento", "🚶 Normal", "🏃 Rápido", "⚡ Turbo"])
        self.combo_speed.setCurrentIndex(1)
        self.combo_speed.setFixedWidth(110)
        self.combo_speed.currentIndexChanged.connect(self._on_speed)
        tb.addWidget(self.combo_speed)

        tb.addWidget(_sep())

        # Estrategia de memoria
        tb.addWidget(_lbl("  Mem:"))
        self.combo_mem = QComboBox()
        self.combo_mem.addItems(["First Fit", "Best Fit", "Worst Fit"])
        self.combo_mem.setFixedWidth(90)
        self.combo_mem.currentIndexChanged.connect(
            lambda i: self.engine.change_alloc_strategy(["first", "best", "worst"][i])
        )
        tb.addWidget(self.combo_mem)

    def _build_central(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; }")
        self.setCentralWidget(scroll_area)

        central = QWidget()
        scroll_area.setWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 4)
        root.setSpacing(4)

        global_v_split = QSplitter(Qt.Orientation.Vertical)
        global_v_split.setStyleSheet("QSplitter::handle { background: #333; height: 3px; }")
        root.addWidget(global_v_split, stretch=1)

        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.setStyleSheet("QSplitter::handle { background: #333; width: 3px; }")
        global_v_split.addWidget(main_split)

        # ── Panel izquierdo ───────────────────────────────────────────────────
        left_split = QSplitter(Qt.Orientation.Vertical)
        left_split.setMinimumWidth(260)
        left_split.setMaximumWidth(340)

        self.cpu_widget = CPUWidget(num_cores=len(self.engine.cores))
        self.cpu_widget.setMinimumHeight(150)
        left_split.addWidget(self.cpu_widget)

        self.memory_widget = MemoryWidget()
        self.memory_widget.setMinimumHeight(300)
        left_split.addWidget(self.memory_widget)

        main_split.addWidget(left_split)

        # ── Panel central ─────────────────────────────────────────────────────
        center_split = QSplitter(Qt.Orientation.Vertical)
        center_split.setMinimumWidth(400)

        self.queue_widget = QueueWidget()
        self.queue_widget.setMinimumHeight(180)
        center_split.addWidget(self.queue_widget)

        self.pcb_table = PCBTableWidget()
        self.pcb_table.setMinimumHeight(200)
        center_split.addWidget(self.pcb_table)

        main_split.addWidget(center_split)

        # ── Panel derecho ─────────────────────────────────────────────────────
        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.setMinimumWidth(260)
        right_split.setMaximumWidth(340)

        self.io_widget = IOStatusWidget()
        self.io_widget.setMinimumHeight(200)
        right_split.addWidget(self.io_widget)

        self.metrics_widget = MetricsWidget()
        self.metrics_widget.setMinimumHeight(180)
        right_split.addWidget(self.metrics_widget)

        main_split.addWidget(right_split)
        main_split.setSizes([280, 800, 280])

        # ── Timeline ──────────────────────────────────────────────────────────
        self.timeline_widget = TimelineWidget()
        self.timeline_widget.setMinimumHeight(130)
        global_v_split.addWidget(self.timeline_widget)

        # ── Log ───────────────────────────────────────────────────────────────
        self.log_widget = LogWidget()
        self.log_widget.setMinimumHeight(160)
        global_v_split.addWidget(self.log_widget)
        
        global_v_split.setSizes([600, 150, 150])

    def _build_statusbar(self):
        sb = self.statusBar()
        sb.setStyleSheet(f"""
            QStatusBar {{
                background:{Colors.BG_BASE};
                color:{Colors.TEXT_SEC};
                border-top:1px solid {Colors.BORDER};
                font-size:8pt;
            }}
        """)
        self.sb_tick    = QLabel("  T=0")
        self.sb_sched   = QLabel(f"  {self.engine.config.scheduler_algorithm}")
        self.sb_procs   = QLabel("  Procesos: 0")
        self.sb_mem     = QLabel("  RAM: 0%")
        self.sb_frag    = QLabel("  Frag: 0%")
        self.sb_ctx     = QLabel("  CTX: 0")

        for w in [self.sb_tick, QLabel(" | "), self.sb_sched, QLabel(" | "),
                  self.sb_procs, QLabel(" | "), self.sb_mem, QLabel(" | "),
                  self.sb_frag, QLabel(" | "), self.sb_ctx]:
            sb.addWidget(w)

        sb.addPermanentWidget(_lbl(
            "PatatOS v2.0 — Simulador Educativo SO", Colors.TEXT_MUTED
        ))

    # ─────────────────────────────────────────────────────────────────────────
    # Slots de control
    # ─────────────────────────────────────────────────────────────────────────

    def _on_start(self):
        self.clock.start()
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)

    def _on_pause(self):
        self.clock.pause()
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)

    def _on_reset(self):
        reply = QMessageBox.question(
            self, "Confirmar Reset",
            "¿Reiniciar la simulación? Se perderán todos los datos.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.clock.pause()
            self.clock.reset()
            self.engine.reset()
            self._log_offset = 0
            self.log_widget.clear_log()
            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self._refresh()

    def _on_speed(self, idx: int):
        speeds = [SimClock.SPEED_SLOW, SimClock.SPEED_NORMAL,
                  SimClock.SPEED_FAST, SimClock.SPEED_TURBO]
        self.clock.set_speed(speeds[idx])

    def _on_new_process(self):
        dlg = _NewProcessDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.get_data()
            self.engine.create_process(**d)
            self._refresh()

    def _on_tick(self, tick: int):
        """Callback del clock: ejecutar el tick del engine y refrescar la UI."""
        self.engine.tick(tick)
        self._refresh()

    # ─────────────────────────────────────────────────────────────────────────
    # Refresco de UI
    # ─────────────────────────────────────────────────────────────────────────

    def _refresh(self):
        """Lee el snapshot del engine y actualiza todos los widgets."""
        snap = self.engine.get_snapshot()

        self.cpu_widget.update(snap["cores"])
        self.memory_widget.update(snap["memory"], snap["memory_stats"], snap.get("mmu_table", {}))
        self.queue_widget.update(snap["ready_queues"], snap["waiting"])
        self.pcb_table.update(snap["all_processes"])
        self.io_widget.update(snap["io_devices"])
        self.metrics_widget.update(snap["metrics"])
        self.timeline_widget.update(snap["timeline"], len(snap["cores"]))

        # Log incremental
        new_msgs = snap["log"][self._log_offset:]
        if new_msgs:
            self.log_widget.append_messages(new_msgs)
            self._log_offset = len(snap["log"])

        # Status bar
        t = snap["tick"]
        m = snap["memory_stats"]
        procs = snap["all_processes"]
        active = sum(1 for p in procs if str(p.state) != "ProcessState.TERMINATED")
        self.sb_tick.setText(f"  T={t}")
        self.sb_procs.setText(f"  Procesos: {active}")
        self.sb_mem.setText(f"  RAM: {m['usage_pct']}%")
        self.sb_frag.setText(f"  Frag: {m['fragmentation']}%")
        self.sb_ctx.setText(f"  CTX: {self.engine.metrics.context_switches}")


# ── Diálogo rápido de proceso nuevo ──────────────────────────────────────────

class _NewProcessDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo Proceso")
        self.setModal(True)
        self.setFixedSize(360, 260)
        self.setStyleSheet(get_main_stylesheet())

        g = __import__("PySide6.QtWidgets", fromlist=["QGridLayout"]).QGridLayout(self)
        g.setSpacing(10)
        g.setContentsMargins(20, 20, 20, 16)

        def row(r, label, widget):
            g.addWidget(QLabel(label), r, 0)
            g.addWidget(widget, r, 1)

        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("vacío = auto")
        row(0, "Nombre:", self.edit_name)

        self.spin_burst = QSpinBox()
        self.spin_burst.setRange(3, 100)
        self.spin_burst.setValue(20)
        row(1, "Burst (ticks):", self.spin_burst)

        self.spin_prio = QSpinBox()
        self.spin_prio.setRange(0, 9)
        self.spin_prio.setValue(5)
        row(2, "Prioridad (0=alta):", self.spin_prio)

        self.spin_mem = QSpinBox()
        self.spin_mem.setRange(4, 256)
        self.spin_mem.setValue(32)
        row(3, "Memoria (MB):", self.spin_mem)

        self.combo_type = QComboBox()
        self.combo_type.addItems(["CPU_BOUND", "IO_BOUND", "INTERACTIVE", "SYSTEM"])
        row(4, "Tipo:", self.combo_type)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("✓  Crear")
        btn_ok.setObjectName("btn_start")
        btn_ok.clicked.connect(self.accept)
        btns.addWidget(btn_cancel)
        btns.addStretch()
        btns.addWidget(btn_ok)

        btn_widget = QWidget()
        btn_widget.setLayout(btns)
        g.addWidget(btn_widget, 5, 0, 1, 2)

    def get_data(self) -> dict:
        return {
            "name":         self.edit_name.text() or None,
            "burst_time":   self.spin_burst.value(),
            "priority":     self.spin_prio.value(),
            "memory_size":  self.spin_mem.value(),
            "process_type": self.combo_type.currentText(),
        }
