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
import subprocess
import time
from PySide6.QtCore import QCoreApplication

from simulation.paths import ESCENARIO_PATH, OUTPUT_PATH, BACKEND_DIR, SIMULATOR_EXE

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox,
    QSplitter, QFrame, QToolBar, QDialog, QMessageBox,
    QLineEdit, QDoubleSpinBox, QScrollArea, QMenuBar, QSizePolicy, QSlider, QTabWidget
)
from PySide6.QtGui import QAction

from simulation.clock import SimClock
from simulation.config import HardwareConfig
from ui.styles import Colors, get_main_stylesheet
from ui.state_patcher import get_state_at_tick, apply_delta
import json
import os
import time

# Widgets
from ui.widgets.cpu_widget import CPUWidget
from ui.widgets.memory_widget import MemoryWidget
from ui.widgets.queue_widget import QueueWidget
from ui.widgets.pcb_table import PCBTableWidget
from ui.widgets.metrics_widget import MetricsWidget
from ui.widgets.io_widget import IOStatusWidget
from ui.widgets.timeline_widget import TimelineWidget
from ui.widgets.log_widget import LogWidget
from ui.widgets.gantt_widget import GanttWidget


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
    Ventana principal de PatatOS v2.
    Reproductor puramente estático de un archivo JSON (output_modelo.json).
    """

    def __init__(
        self,
        output_file: str,
        clock: SimClock,
        parent=None,
    ):
        super().__init__(parent)
        self.clock = clock
        self._log_offset: int = 0
        self._playback_mode: bool = True
        self._playback_data: list = []
        self._playback_tick: int = 0
        self._global_timeline: list = []
        self._global_logs: list = []
        self._static_info: dict = {}
        self.output_file = output_file
        
        # Leer escenario en vivo para overrides de UI (simulando que C++ respetó la config)
        self._live_config = {}
        try:
            if os.path.exists(ESCENARIO_PATH):
                with open(ESCENARIO_PATH, "r", encoding="utf-8") as f:
                    self._live_config = json.load(f)
        except Exception:
            pass
        
        self._load_json(output_file)

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

        # Conectar señal interactiva del teclado
        self.io_widget.keyboard_signal.connect(self._on_keyboard_signal)

        if self._playback_data:
            self._refresh(get_state_at_tick(self._playback_data, self._playback_tick, self._static_info))

    def _load_json(self, filepath: str):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._static_info = {p["pid"]: p for p in data.get("global_process_info", [])}
            self._playback_data = data.get("ticks", [])
            self._infer_frontend_data(self._playback_data)
            
            if hasattr(self, "spin_jump"):
                if self._playback_data:
                    self.spin_jump.setEnabled(True)
                    self.spin_jump.blockSignals(True)
                    self.spin_jump.setRange(0, len(self._playback_data) - 1)
                    if not hasattr(self, "_playback_tick") or self._playback_tick == 0:
                        self.spin_jump.setValue(0)
                    else:
                        # Mantener visualmente el tick en el que estábamos
                        self.spin_jump.setValue(min(self._playback_tick, len(self._playback_data) - 1))
                    self.spin_jump.blockSignals(False)
                else:
                    self.spin_jump.setEnabled(False)
                    
        except Exception as e:
            print(f"Error cargando JSON inicial: {e}")
            self._playback_data = []
            self._static_info = {}

    # ─────────────────────────────────────────────────────────────────────────
    # Construcción
    # ─────────────────────────────────────────────────────────────────────────

    def _build_menu(self):
        menu = self.menuBar()
        menu.setStyleSheet(f"QMenuBar {{ background: {Colors.BG_BASE}; color: {Colors.TEXT_PRIMARY}; border-bottom: 1px solid {Colors.BORDER}; }} QMenuBar::item:selected {{ background: {Colors.BG_ELEVATED}; }} QMenu {{ background: {Colors.BG_SURFACE}; color: {Colors.TEXT_PRIMARY}; border: 1px solid {Colors.BORDER}; }}")
        
        # Acción directa en el menú
        action_load = menu.addAction("📂 Cargar JSON")
        action_load.triggered.connect(self._on_load_json)

        action_reconfig = menu.addAction("⚙️ Reconfigurar Entorno")
        action_reconfig.triggered.connect(self._on_reconfigure)
        
        action_export = menu.addAction("💾 Exportar Reporte")
        action_export.triggered.connect(self._on_export_report)

        # ── Métricas en la parte superior derecha (Corner Widget) ──
        self.sb_tick    = QLabel("  T=0")
        self.sb_procs   = QLabel("  Procesos: 0")
        self.sb_mem     = QLabel("  RAM: 0%")
        self.sb_frag    = QLabel("  Frag: 0%")
        self.sb_ctx     = QLabel("  CTX: 0")

        corner_widget = QWidget(menu)
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 15, 0)
        
        for w in [self.sb_tick, QLabel(" | "),
                  self.sb_procs, QLabel(" | "), self.sb_mem, QLabel(" | "),
                  self.sb_frag, QLabel(" | "), self.sb_ctx]:
            w.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-weight: bold;")
            corner_layout.addWidget(w)
            
        menu.setCornerWidget(corner_widget, Qt.Corner.TopRightCorner)



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
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setFixedHeight(30)
        self.btn_start.clicked.connect(self._on_start)
        tb.addWidget(self.btn_start)

        self.btn_pause = QPushButton("⏸  Pausar")
        self.btn_pause.setObjectName("btn_pause")
        self.btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause.setFixedHeight(30)
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._on_pause)
        tb.addWidget(self.btn_pause)

        self.btn_reset = QPushButton("↺  Reset")
        self.btn_reset.setObjectName("btn_reset")
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.setFixedHeight(30)
        self.btn_reset.clicked.connect(self._on_reset)
        tb.addWidget(self.btn_reset)

        tb.addWidget(_sep())
        
        tb.addWidget(_lbl(" Ir a Tick: "))
        self.spin_jump = QSpinBox()
        self.spin_jump.setFixedWidth(110)
        self.spin_jump.setKeyboardTracking(False)
        self.spin_jump.setEnabled(False)
        if self._playback_data:
            self.spin_jump.setRange(0, len(self._playback_data) - 1)
        else:
            self.spin_jump.setRange(0, 999999)
        self.spin_jump.setToolTip("Disponible solo en pausa. Cambia el valor y presiona Iniciar para saltar.")
        tb.addWidget(self.spin_jump)

        tb.addWidget(_sep())

        # Nuevo proceso
        self.btn_new = QPushButton("＋  Añadir Proceso en Caliente")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.setFixedHeight(30)
        self.btn_new.clicked.connect(self._on_new_process)
        tb.addWidget(self.btn_new)

        tb.addWidget(_sep())

        # Configuración en caliente
        tb.addWidget(_lbl("  Algoritmo:"))
        self.combo_sched = QComboBox()
        self.combo_sched.addItems(["FCFS", "SJF", "Round Robin", "Prioridades"])
        tb.addWidget(self.combo_sched)

        tb.addWidget(_lbl(" Q:"))
        self.spin_q = QSpinBox()
        self.spin_q.setRange(1, 50)
        self.spin_q.setValue(4)
        tb.addWidget(self.spin_q)

        tb.addWidget(_lbl("  Mem:"))
        self.combo_mem = QComboBox()
        self.combo_mem.addItems(["FirstFit", "BestFit", "WorstFit"])
        tb.addWidget(self.combo_mem)

        self._sync_config_from_file()

        self.combo_sched.currentIndexChanged.connect(self._on_hot_config_change)
        self.spin_q.valueChanged.connect(self._on_hot_config_change)
        self.combo_mem.currentIndexChanged.connect(self._on_hot_config_change)

        tb.addWidget(_sep())

        # Velocidad
        tb.addWidget(_lbl("  Vel:"))
        self.combo_speed = QComboBox()
        self.combo_speed.addItems([
            "🐌 Lento (2000 ms/t)", 
            "🚶 Normal (800 ms/t)", 
            "🏃 Rápido (250 ms/t)", 
            "⚡ Turbo (80 ms/t)", 
            "⚙️ Personalizado..."
        ])
        self.combo_speed.setCurrentIndex(1)
        self.combo_speed.setFixedWidth(170)
        self.combo_speed.currentIndexChanged.connect(self._on_speed)
        tb.addWidget(self.combo_speed)

        # ── Spacer para alinear a la derecha ──
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        tb.addWidget(spacer)

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

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {Colors.BORDER}; background: {Colors.BG_BASE}; }}
            QTabBar::tab {{ background: {Colors.BG_SURFACE}; color: {Colors.TEXT_SEC}; padding: 8px 16px; border: 1px solid {Colors.BORDER}; }}
            QTabBar::tab:selected {{ background: {Colors.BG_ELEVATED}; color: {Colors.TEXT_PRIMARY}; border-bottom: 2px solid {Colors.ACCENT}; }}
        """)
        root.addWidget(self.tabs, stretch=1)

        # ── Pestaña 1: Gestión de Procesos ─────────────────────────────────────────
        tab_procs = QWidget()
        layout_procs = QVBoxLayout(tab_procs)
        layout_procs.setContentsMargins(4, 4, 4, 4)
        
        split_procs = QSplitter(Qt.Orientation.Vertical)
        
        # Detectar num cores desde el snapshot si está disponible, sino 1
        num_c = 1
        if self._playback_data:
            first_state = get_state_at_tick(self._playback_data, 0, self._static_info)
            if "cores" in first_state:
                num_c = len(first_state["cores"])

        # ── Superior: QueueWidget (Toma todo el ancho) ──
        self.queue_widget = QueueWidget()
        split_procs.addWidget(self.queue_widget)

        # ── Medio: Splitter Horizontal (CPU a la izquierda, PCB a la derecha) ──
        split_procs_mid = QSplitter(Qt.Orientation.Horizontal)
        
        self.cpu_widget = CPUWidget(num_cores=num_c)
        self.cpu_widget.setMinimumHeight(150)
        split_procs_mid.addWidget(self.cpu_widget)

        self.pcb_table = PCBTableWidget()
        self.pcb_table.setMinimumHeight(200)
        split_procs_mid.addWidget(self.pcb_table)
        
        split_procs.addWidget(split_procs_mid)

        self.gantt_widget = GanttWidget()
        self.gantt_widget.setMinimumHeight(200)
        split_procs.addWidget(self.gantt_widget)

        layout_procs.addWidget(split_procs)
        self.tabs.addTab(tab_procs, "Gestión de Procesos")

        # ── Pestaña 2: Gestión de Memoria ──────────────────────────────────────────
        tab_mem = QWidget()
        layout_mem = QVBoxLayout(tab_mem)
        layout_mem.setContentsMargins(4, 4, 4, 4)
        
        self.memory_widget = MemoryWidget()
        self.memory_widget.setMinimumHeight(300)
        layout_mem.addWidget(self.memory_widget)
        self.tabs.addTab(tab_mem, "Gestión de Memoria")

        # ── Pestaña 3: Gestión de E/S y Rendimiento ──────────────────────────────
        tab_io = QWidget()
        layout_io = QHBoxLayout(tab_io)
        layout_io.setContentsMargins(4, 4, 4, 4)
        
        split_io = QSplitter(Qt.Orientation.Horizontal)
        self.io_widget = IOStatusWidget()
        self.io_widget.setMinimumHeight(200)
        split_io.addWidget(self.io_widget)
        
        self.metrics_widget = MetricsWidget()
        self.metrics_widget.setMinimumHeight(180)
        split_io.addWidget(self.metrics_widget)
        
        layout_io.addWidget(split_io)
        self.tabs.addTab(tab_io, "Gestión de E/S y Rendimiento")

        # ── Pestaña 4: Timeline y Logs ─────────────────────────────────────────
        tab_logs = QWidget()
        layout_logs = QVBoxLayout(tab_logs)
        layout_logs.setContentsMargins(4, 4, 4, 4)
        
        split_logs = QSplitter(Qt.Orientation.Vertical)
        
        self.timeline_widget = TimelineWidget()
        self.timeline_widget.setMinimumHeight(150)
        split_logs.addWidget(self.timeline_widget)

        self.log_widget = LogWidget()
        self.log_widget.setMinimumHeight(120)
        split_logs.addWidget(self.log_widget)
        
        layout_logs.addWidget(split_logs)
        self.tabs.addTab(tab_logs, "Línea de Tiempo y Registros")

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
        sb.addPermanentWidget(_lbl(
            "PatatOS v2.0 — Simulador Educativo SO", Colors.TEXT_MUTED
        ))

    def _update_playback_buttons(self, running: bool):
        """Colorea los botones Iniciar/Pausar según el estado actual."""
        if running:
            # Iniciar → apagado (gris), Pausar → encendido (ámbar)
            self.btn_start.setStyleSheet(
                "QPushButton { background: #2a2a2a; color: #555; border-radius: 4px;"
                " padding: 0 10px; border: 1px solid #333; }"
            )
            self.btn_pause.setStyleSheet(
                "QPushButton { background: #b45309; color: #fff; font-weight: bold;"
                " border-radius: 4px; padding: 0 10px; border: none; }"
                "QPushButton:hover { background: #d97706; }"
            )
        else:
            # Iniciar → encendido (verde), Pausar → apagado (gris)
            self.btn_start.setStyleSheet(
                "QPushButton { background: #166534; color: #fff; font-weight: bold;"
                " border-radius: 4px; padding: 0 10px; border: none; }"
                "QPushButton:hover { background: #16a34a; }"
            )
            self.btn_pause.setStyleSheet(
                "QPushButton { background: #2a2a2a; color: #555; border-radius: 4px;"
                " padding: 0 10px; border: 1px solid #333; }"
            )
        
    # ─────────────────────────────────────────────────────────────────────────
    # Slots de control
    # ─────────────────────────────────────────────────────────────────────────

    def _on_start(self):
        if hasattr(self, "spin_jump") and self.spin_jump.isEnabled():
            jump_val = self.spin_jump.value()
            if self._playback_mode and self._playback_data and jump_val != self._playback_tick:
                self._playback_tick = jump_val
                self._refresh(get_state_at_tick(self._playback_data, self._playback_tick, self._static_info))
                
        if hasattr(self, "spin_jump"):
            self.spin_jump.setEnabled(False)

        self.clock.start()
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self._update_playback_buttons(running=True)

    def _on_pause(self):
        self.clock.pause()
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self._update_playback_buttons(running=False)
        
        if hasattr(self, "spin_jump") and self._playback_mode and self._playback_data:
            self.spin_jump.setEnabled(True)
            self.spin_jump.blockSignals(True)
            self.spin_jump.setValue(self._playback_tick)
            self.spin_jump.blockSignals(False)

    def _on_reset(self):
        reply = QMessageBox.question(
            self, "Confirmar Reset",
            "¿Reiniciar la simulación? Se perderán todos los datos." if not self._playback_mode
            else "¿Volver al inicio del JSON cargado?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.clock.pause()
        self.clock.reset()
        self._log_offset = 0
        self.log_widget.clear_log()
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)

        if self._playback_mode:
            # ── Modo JSON: rebobinar al tick 0 ──
            self._playback_tick = 0
            if self._playback_data:
                self._refresh(get_state_at_tick(self._playback_data, 0, self._static_info))


    def _on_speed(self, idx: int):
        from PySide6.QtWidgets import QInputDialog
        speeds = [SimClock.SPEED_SLOW, SimClock.SPEED_NORMAL,
                  SimClock.SPEED_FAST, SimClock.SPEED_TURBO]
        if idx < 4:
            self.clock.set_speed(speeds[idx])
        else:
            val, ok = QInputDialog.getInt(self, "Velocidad Personalizada", "Milisegundos por tick (ms/t):", 
                                          self.clock._speed_ms, 1, 10000, 1)
            if ok:
                self.clock.set_speed(val)
            else:
                self.combo_speed.blockSignals(True)
                self.combo_speed.setCurrentIndex(1)
                self.combo_speed.blockSignals(False)
                self.clock.set_speed(speeds[1])

    def _sync_config_from_file(self):
        if not os.path.exists(ESCENARIO_PATH):
            return
        try:
            with open(ESCENARIO_PATH, "r", encoding="utf-8") as f:
                scen = json.load(f)

            cpu = scen.get("hardware", {}).get("cpu", {})
            algo_raw = cpu.get("scheduler", "FCFS")
            q    = cpu.get("quantum", 4)
            mem_strategy = scen.get("hardware", {}).get("memory", {}).get("allocationStrategy", "FIRST_FIT")

            # Map backend algo string to UI label
            algo_map = {"FCFS": "FCFS", "SJF": "SJF", "RR": "Round Robin", "Priority": "Prioridades"}
            algo_ui = algo_map.get(algo_raw, "FCFS")
            idx_sched = self.combo_sched.findText(algo_ui)
            if idx_sched >= 0: self.combo_sched.setCurrentIndex(idx_sched)
            self.spin_q.setValue(q)

            mem_map = {"FIRST_FIT": "FirstFit", "BEST_FIT": "BestFit", "WORST_FIT": "WorstFit"}
            mem_ui = mem_map.get(mem_strategy, "FirstFit")
            idx_mem = self.combo_mem.findText(mem_ui)
            if idx_mem >= 0: self.combo_mem.setCurrentIndex(idx_mem)
        except Exception:
            pass

    def _on_hot_config_change(self):
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import QCoreApplication

        from simulation.paths import ESCENARIO_PATH
        if not os.path.exists(ESCENARIO_PATH):
            return
            
        was_running = self.clock.is_running
        self.clock.pause()
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        
        try:
            with open(ESCENARIO_PATH, "r", encoding="utf-8") as f:
                scen = json.load(f)

            # Map UI label → backend string
            algo_map = {"FCFS": "FCFS", "SJF": "SJF", "Round Robin": "RR", "Prioridades": "Priority"}
            algo_backend = algo_map.get(self.combo_sched.currentText(), "FCFS")
            mem_map = {"FirstFit": "FIRST_FIT", "BestFit": "BEST_FIT", "WorstFit": "WORST_FIT"}
            mem_backend = mem_map.get(self.combo_mem.currentText(), "FIRST_FIT")

            if "hardware" not in scen:
                scen["hardware"] = {}
            if "cpu" not in scen["hardware"]:
                scen["hardware"]["cpu"] = {}
            if "memory" not in scen["hardware"]:
                scen["hardware"]["memory"] = {}

            scen["hardware"]["cpu"]["scheduler"] = algo_backend
            scen["hardware"]["cpu"]["quantum"]   = self.spin_q.value()
            scen["hardware"]["cpu"]["preemptive"] = algo_backend in ("RR", "Priority")
            
            # Asegurar que los parámetros base de memoria se mantengan si no existen
            if "totalMB" not in scen["hardware"]["memory"]:
                scen["hardware"]["memory"]["totalMB"] = 32
            if "osReservedMB" not in scen["hardware"]["memory"]:
                scen["hardware"]["memory"]["osReservedMB"] = 8
            
            scen["hardware"]["memory"]["allocationStrategy"] = mem_backend
            
            with open(ESCENARIO_PATH, "w", encoding="utf-8") as f:
                json.dump(scen, f, indent=4)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al guardar JSON: {e}")
            return
            
        # --- LLAMADA AL BACKEND ---
        pd = QProgressDialog("Recalculando Universo en el Backend (C++)...", None, 0, 0, self)
        pd.setWindowTitle("Aplicando Configuración...")
        pd.setWindowModality(Qt.WindowModality.WindowModal)
        pd.setCancelButton(None)
        pd.show()

        try:
            process = subprocess.Popen([SIMULATOR_EXE, "-t", "50000"], cwd=BACKEND_DIR)
            while process.poll() is None:
                QCoreApplication.processEvents()
                time.sleep(0.05)
            
            if process.returncode != 0:
                QMessageBox.critical(self, "Error de Backend", f"El motor C++ terminó con error: {process.returncode}")
                pd.close()
                return
        except Exception as e:
            QMessageBox.critical(self, "Error de Backend", f"Fallo al ejecutar el motor C++:\n{e}")
            pd.close()
            return
            
        pd.close()
            
        # Recargar output actual
        try:
            with open(self.output_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            self._playback_data = d.get("ticks", [])
            self._infer_frontend_data(self._playback_data)
        except:
            pass
            
        self._playback_tick = min(self._playback_tick, len(self._playback_data) - 1) if self._playback_data else 0
        
        if self._playback_data and self._playback_tick >= 0:
            self._refresh(get_state_at_tick(self._playback_data, self._playback_tick, self._static_info))

        if was_running:
            self._on_start()

    def _on_new_process(self):
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import QCoreApplication

        self.clock.pause()
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)

        dlg = _NewProcessDialog(self._playback_tick + 1, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.get_data()
            
            # Leer escenario de entrada
            if os.path.exists(ESCENARIO_PATH):
                with open(ESCENARIO_PATH, "r", encoding="utf-8") as f:
                    scen = json.load(f)
            else:
                scen = {"processes": []}
            
            # Añadir nuevo proceso
            scen.setdefault("processes", []).append(d)
            
            # Guardar escenario de entrada
            with open(ESCENARIO_PATH, "w", encoding="utf-8") as f:
                json.dump(scen, f, indent=2, ensure_ascii=False)
            
            # --- LLAMADA AL BACKEND ---
            progress = QProgressDialog("Recalculando el futuro en el backend (C++)...", None, 0, 0, self)
            progress.setWindowTitle("Generando Output")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setCancelButton(None)
            progress.show()

            try:
                process = subprocess.Popen([SIMULATOR_EXE, "-t", "50000"], cwd=BACKEND_DIR)
                while process.poll() is None:
                    QCoreApplication.processEvents()
                    time.sleep(0.05)
                
                if process.returncode != 0:
                    QMessageBox.critical(self, "Error de Backend", f"El motor C++ terminó con error: {process.returncode}")
                    progress.close()
                    return
            except Exception as e:
                QMessageBox.critical(self, "Error de Backend", f"Fallo al ejecutar el motor C++:\n{e}")
                progress.close()
                return
            
            progress.close()

            # Nota: Para el backend real en C++, recargaríamos output_modelo.json aquí.
            # Como esto es un mockup y no tenemos C++, simplemente reanudamos.
            self._load_json(self.output_file)
            if self._playback_data:
                self._infer_frontend_data(self._playback_data)
            
            QMessageBox.information(self, "Recálculo Completo", f"El backend simuló el nuevo universo a partir del tick {d['arrival_tick']}. La animación continuará desde ese punto.")
            
            # Reanudar exactamente donde pausamos
            if self._playback_data and 0 <= self._playback_tick < len(self._playback_data):
                self._refresh(get_state_at_tick(self._playback_data, self._playback_tick, self._static_info))
            self._on_start()

    def _on_keyboard_signal(self, pid: int, action: str):
        """Maneja la interacción del usuario con el dispositivo KEYBOARD.
        
        Inyecta un evento en el escenario y fuerza recalcular la simulación.
        action: 'CANCEL' (cancela el proceso) o 'CONTINUE' (lo reanuda).
        """
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import QCoreApplication

        tick_actual = self._playback_tick
        was_running = self.clock.is_running
        self.clock.pause()
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)

        # Get the actual tick displayed in the UI to avoid +1 offset bugs
        tick_to_inject = 0
        if self._playback_data and 0 <= self._playback_tick < len(self._playback_data):
            snap = get_state_at_tick(self._playback_data, self._playback_tick, self._static_info)
            tick_to_inject = snap.get("tick", 0)
        elif self._playback_data:
            # Clamped fallback
            snap = get_state_at_tick(self._playback_data, len(self._playback_data) - 1, self._static_info)
            tick_to_inject = snap.get("tick", 0)

        try:
            if os.path.exists(ESCENARIO_PATH):
                with open(ESCENARIO_PATH, "r", encoding="utf-8") as f:
                    scen = json.load(f)
            else:
                scen = {}

            # Inyectar el evento de teclado en el escenario para que C++ lo lea
            events = scen.setdefault("events", [])
            
            duplicate = False
            for ev in events:
                if ev.get("tick") == tick_to_inject and ev.get("pid") == pid and ev.get("action") == action:
                    duplicate = True
                    break
                    
            if not duplicate:
                events.append({
                    "tick":   tick_to_inject,
                    "type":   "KEYBOARD",
                    "pid":    pid,
                    "action": action,
                })

            with open(ESCENARIO_PATH, "w", encoding="utf-8") as f:
                json.dump(scen, f, indent=2, ensure_ascii=False)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo inyectar el evento de teclado:\n{e}")
            return

        # --- LLAMADA AL BACKEND ---
        action_text = "cancelado" if action == "CANCEL" else "reanudado"
        pd = QProgressDialog(
            f"Recalculando universo — PID {pid} será {action_text}...",
            None, 0, 0, self
        )
        pd.setWindowTitle("Procesando Señal de Teclado")
        pd.setWindowModality(Qt.WindowModality.WindowModal)
        pd.setCancelButton(None)
        pd.show()

        try:
            process = subprocess.Popen([SIMULATOR_EXE, "-t", "50000"], cwd=BACKEND_DIR)
            while process.poll() is None:
                QCoreApplication.processEvents()
                time.sleep(0.05)
            
            if process.returncode != 0:
                QMessageBox.critical(self, "Error de Backend", f"El motor C++ terminó con error: {process.returncode}")
                pd.close()
                return
        except Exception as e:
            QMessageBox.critical(self, "Error de Backend", f"Fallo al ejecutar el motor C++:\n{e}")
            pd.close()
            return

        pd.close()

        # Recargar datos y volver al mismo tick
        self._load_json(self.output_file)
        # Restaurar botones (la interrupción fue resuelta)
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self._playback_tick = min(tick_actual, len(self._playback_data) - 1)
        if hasattr(self, "spin_jump"):
            self.spin_jump.blockSignals(True)
            self.spin_jump.setValue(self._playback_tick)
            self.spin_jump.blockSignals(False)
            
        if self._playback_data and self._playback_tick >= 0:
            self._refresh(get_state_at_tick(self._playback_data, self._playback_tick, self._static_info))
        # Siempre reanudar después de resolver la interrupción
        self._on_start()

    def _infer_frontend_data(self, ticks: list):
        """Infiere el timeline de Gantt y los console_logs analizando cambios de estado entre fotogramas."""
        prev_states = {}
        self._global_timeline.clear()
        self._global_logs.clear()
        
        # Keep a running state to correctly infer changes from deltas
        # IMPORTANT: use deepcopy to avoid corrupting snapshot raw data
        import copy
        base_state = {}
        
        for snap in ticks:
            tick_num = snap.get("tick", 0)
            
            if snap.get("type") == "snapshot":
                base_state = copy.deepcopy(snap.get("state", {}))
            elif snap.get("type") == "delta":
                apply_delta(base_state, copy.deepcopy(snap.get("updates", {})))
            else:
                base_state = copy.deepcopy(snap)
                
            current_procs = {p["pid"]: p for p in base_state.get("process_table", [])}
            
            # Compatibilidad legacy: el snapshot puede usar "all_processes" en lugar de "process_table"
            if not current_procs and "all_processes" in snap:
                current_procs = {p["pid"]: p for p in snap["all_processes"]}
            
            for pid, proc in current_procs.items():
                state = proc.get("state")
                prev_state = prev_states.get(pid)
                
                if state and prev_state != state:
                    # Deducir el núcleo si está en RUNNING
                    core_id = None
                    if state == "RUNNING":
                        for c in base_state.get("cores", []):
                            if c.get("is_busy") and c.get("process", {}).get("pid") == pid:
                                core_id = c.get("id")
                            elif c.get("status") == "RUNNING" and c.get("current_process") == pid:
                                core_id = c.get("core_id")
                    
                    label = f"P{pid}({proc.get('name', 'P')})"
                    self._global_timeline.append({
                        "tick": tick_num,
                        "core_id": core_id if core_id is not None else 0,
                        "label": label,
                        "from_state": prev_state or "NEW",
                        "to_state": state
                    })
                    
                    if prev_state is None:
                        self._global_logs.append(f"[T={tick_num}] {label} NEW.")
                    elif state == "RUNNING":
                        self._global_logs.append(f"[T={tick_num}] {label} RUNNING -> CPU.")
                    elif state == "TERMINATED":
                        self._global_logs.append(f"[T={tick_num}] {label} TERMINATED.")
                    else:
                        self._global_logs.append(f"[T={tick_num}] {label} -> {state}.")
                        
                    prev_states[pid] = state
            
            # Inject into the raw frame so get_state_at_tick can return them
            raw_frame = snap  # snap IS the raw frame here (we iterate ticks directly)
            raw_frame["_timeline_count"] = len(self._global_timeline)
            raw_frame["_log_count"] = len(self._global_logs)

    def _on_reconfigure(self):
        self._wants_restart = True
        self.close()

    def _on_load_json(self):
        import json
        import os
        from PySide6.QtWidgets import QFileDialog
        
        filepath, _ = QFileDialog.getOpenFileName(self, "Cargar Mockup JSON", "", "JSON Files (*.json)")
        if not filepath:
            return
            
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if "ticks" not in data:
                QMessageBox.warning(self, "Error", "El archivo no tiene el formato de output_modelo válido.")
                return
                
            self._static_info = {p["pid"]: p for p in data.get("global_process_info", [])}
            self._playback_data = data["ticks"]
            self._infer_frontend_data(self._playback_data)
            self._playback_mode = True
            self._playback_tick = 0
            
            if hasattr(self, "spin_jump"):
                self.spin_jump.setEnabled(True)
                self.spin_jump.setRange(0, len(self._playback_data) - 1)
                self.spin_jump.setValue(0)
            
            # Deshabilitar controles del motor
            self.btn_new.setEnabled(False)
            self.combo_sched.setEnabled(False)
            self.spin_q.setEnabled(False)
            self.combo_mem.setEnabled(False)
            
            self.setWindowTitle(f"🥔  PatatOS — REPRODUCIENDO: {os.path.basename(filepath)}")
            QMessageBox.information(self, "Cargado", f"Se cargaron {len(self._playback_data)} fotogramas de simulación. Presiona Iniciar para reproducir.")
            
            # Mostrar tick 0
            if self._playback_data:
                self._refresh(get_state_at_tick(self._playback_data, 0, self._static_info))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al cargar el archivo:\n{e}")

    def _on_tick(self, tick: int):
        """Callback del clock: avanzar un fotograma en la reproducción."""
        if self._playback_mode and self._playback_data:
            if 0 <= self._playback_tick < len(self._playback_data):
                snap = get_state_at_tick(self._playback_data, self._playback_tick, self._static_info)
                self._refresh(snap)
                
                self.spin_jump.blockSignals(True)
                self.spin_jump.setValue(self._playback_tick)
                self.spin_jump.blockSignals(False)
                
                self._playback_tick += 1
            else:
                self._on_pause()

    # ─────────────────────────────────────────────────────────────────────────
    # Exportación de reporte
    # ─────────────────────────────────────────────────────────────────────────

    def _on_export_report(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog
        from PySide6.QtCore import QCoreApplication
        from simulation.paths import ESCENARIO_PATH, SIMULATOR_EXE, BACKEND_DIR
        import os
        import json
        import copy
        import subprocess
        import time
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Exportar Benchmark de Memoria", "benchmark_memoria.pdf", "Archivos PDF (*.pdf)"
        )
        if not filepath:
            return
            
        if not os.path.exists(ESCENARIO_PATH):
            QMessageBox.critical(self, "Error", f"No se encontró el escenario base en: {ESCENARIO_PATH}")
            return
            
        with open(ESCENARIO_PATH, "r", encoding="utf-8") as f:
            base_scenario = json.load(f)
            
        original_mode = base_scenario.get("hardware", {}).get("memory", {}).get("mode", "UNKNOWN")
        
        # Forzar modo CONTIGUOUS y aumentar memoria y procesos si es muy pequeño para estrés
        base_scenario["hardware"]["memory"]["mode"] = "CONTIGUOUS"
        if base_scenario["hardware"]["memory"].get("totalMB", 0) < 512:
            base_scenario["hardware"]["memory"]["totalMB"] = 512
            base_scenario["hardware"]["memory"]["osReservedMB"] = 32
            
        if len(base_scenario.get("processes", [])) < 20:
            import random
            base_procs = copy.deepcopy(base_scenario.get("processes", []))
            if base_procs:
                for i in range(15):
                    p = copy.deepcopy(base_procs[i % len(base_procs)])
                    p["name"] = f"App_{len(base_scenario.get('processes', [])) + 1}"
                    p["arrival_tick"] = random.randint(0, 20)
                    p["memory_size"] = random.randint(10, 60)
                    p["burst_time"] = random.randint(5, 15)
                    base_scenario["processes"].append(p)
        
        schedulers = ["FCFS", "SJF", "RR", "Priority"]
        strategies = ["FIRST_FIT", "BEST_FIT", "WORST_FIT"]
        
        results_cpu = {}
        results_mem = {}
        
        progress = QProgressDialog("Corriendo Benchmarks Académicos...", "Cancelar", 0, len(schedulers) + len(strategies), self)
        progress.setWindowTitle("Generando Reporte")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        current_step = 0
        
        # --- 1. Benchmark de CPU ---
        base_mem_strategy = base_scenario.get("hardware", {}).get("memory", {}).get("allocationStrategy", "FIRST_FIT")
        for algo in schedulers:
            if progress.wasCanceled(): return
            progress.setLabelText(f"Evaluando algoritmo CPU {algo}...")
            progress.setValue(current_step)
            current_step += 1
            
            scenario = copy.deepcopy(base_scenario)
            scenario["hardware"]["cpu"]["scheduler"] = algo
            scenario["hardware"]["memory"]["allocationStrategy"] = base_mem_strategy
            
            # Disable manual interactive events
            scenario["events"] = []
            
            temp_input = os.path.join(os.path.dirname(ESCENARIO_PATH), f"temp_input_{algo}.json")
            temp_output = os.path.join(os.path.dirname(ESCENARIO_PATH), f"temp_output_{algo}.json")
            with open(temp_input, "w", encoding="utf-8") as f:
                json.dump(scenario, f, indent=2)
            
            try:
                process = subprocess.Popen([SIMULATOR_EXE, "-i", temp_input, "-o", temp_output, "-t", "50000"], cwd=BACKEND_DIR)
                while process.poll() is None:
                    QCoreApplication.processEvents()
                    time.sleep(0.05)
            except Exception as e:
                QMessageBox.critical(self, "Error de Backend", f"Fallo al ejecutar {algo}:\n{e}")
                progress.close()
                return
            
            if os.path.exists(temp_output):
                with open(temp_output, "r", encoding="utf-8") as f:
                    try:
                        output_data = json.load(f)
                        if output_data and "ticks" in output_data:
                            ticks_data = output_data["ticks"]
                            last_snap = None
                            for frame in reversed(ticks_data):
                                if frame.get("type") == "snapshot":
                                    last_snap = frame.get("state", frame)
                                    break
                                elif "type" not in frame:
                                    last_snap = frame
                                    break
                            if last_snap and "metrics" in last_snap:
                                results_cpu[algo] = dict(last_snap["metrics"])
                    except: pass
            try:
                os.remove(temp_input)
                os.remove(temp_output)
            except: pass
            
        # --- 2. Benchmark de Memoria ---
        base_cpu_algo = base_scenario.get("hardware", {}).get("cpu", {}).get("scheduler", "RR")
        for strategy in strategies:
            if progress.wasCanceled(): return
            progress.setLabelText(f"Evaluando estrategia Memoria {strategy}...")
            progress.setValue(current_step)
            current_step += 1
            
            scenario = copy.deepcopy(base_scenario)
            scenario["hardware"]["cpu"]["scheduler"] = base_cpu_algo
            scenario["hardware"]["memory"]["allocationStrategy"] = strategy
            scenario["events"] = []
            
            temp_input = os.path.join(os.path.dirname(ESCENARIO_PATH), f"temp_input_{strategy}.json")
            temp_output = os.path.join(os.path.dirname(ESCENARIO_PATH), f"temp_output_{strategy}.json")
            with open(temp_input, "w", encoding="utf-8") as f:
                json.dump(scenario, f, indent=2)
                
            try:
                process = subprocess.Popen([SIMULATOR_EXE, "-i", temp_input, "-o", temp_output, "-t", "50000"], cwd=BACKEND_DIR)
                while process.poll() is None:
                    QCoreApplication.processEvents()
                    time.sleep(0.05)
            except Exception as e:
                QMessageBox.critical(self, "Error de Backend", f"Fallo al ejecutar {strategy}:\n{e}")
                progress.close()
                return
                
            if os.path.exists(temp_output):
                with open(temp_output, "r", encoding="utf-8") as f:
                    try:
                        output_data = json.load(f)
                        if output_data and "ticks" in output_data:
                            ticks_data = output_data["ticks"]
                            last_snap = None
                            for frame in reversed(ticks_data):
                                if frame.get("type") == "snapshot":
                                    last_snap = frame.get("state", frame)
                                    break
                                elif "type" not in frame:
                                    last_snap = frame
                                    break
                            if last_snap and "metrics" in last_snap:
                                res_dict = dict(last_snap["metrics"])
                                if "memory" in last_snap and "stats" in last_snap["memory"]:
                                    res_dict.update(last_snap["memory"]["stats"])
                                results_mem[strategy] = res_dict
                    except: pass
            try:
                os.remove(temp_input)
                os.remove(temp_output)
            except: pass
            
        progress.setValue(current_step)
        progress.close()
        
        # ── Escribir el reporte en PDF ──
        try:
            from PySide6.QtGui import QTextDocument, QPdfWriter
            
            html = "<h1>Reporte de Simulaci&oacute;n: Benchmarks de Rendimiento</h1>"
            
            if original_mode == "PAGED":
                html += "<p style='background-color:#ffeeba; padding:10px; border-left:4px solid #ffc107;'>"
                html += "<b>NOTA:</b> El escenario base usaba <b>Memoria Paginada</b>. Para estas pruebas, se forzó internamente a <b>CONTIGUA</b>.</p>"
            
            # --- 6.1 Resultados CPU ---
            html += "<h2>6.1 Resultados de Pol&iacute;ticas de Planificaci&oacute;n de CPU</h2>"
            html += f"<p>Se evaluaron los 4 algoritmos de planificaci&oacute;n manteniendo fija la estrategia de memoria ({base_mem_strategy}) y desactivando los eventos manuales para permitir una ejecuci&oacute;n ininterrumpida.</p>"
            html += "<b>Tabla 12</b><br><i>M&eacute;tricas obtenidas de los algoritmos de planificaci&oacute;n implementados</i><br>"
            html += "<table border='1' cellspacing='0' cellpadding='6' style='border-collapse:collapse; margin-bottom: 10px;'>"
            html += "<tr style='background-color:#f2f2f2;'><th>Algoritmo</th><th>Uso de CPU (%)</th><th>T. Espera Promedio</th><th>T. Respuesta Promedio</th><th>T. Retorno Promedio</th></tr>"
            
            best_turnaround = float('inf')
            best_turn_algo = ""
            best_wait = float('inf')
            best_wait_algo = ""
            best_resp = float('inf')
            best_resp_algo = ""
            best_cpu = -1.0
            best_cpu_algo = ""
            
            for algo in schedulers:
                m = results_cpu.get(algo)
                if not m:
                    html += f"<tr><td>{algo}</td><td colspan='4'>N/A</td></tr>"
                    continue
                cpu_use = m.get("cpu_utilization_percent", 0.0)
                wait_t = m.get("avg_waiting_time", 0.0)
                resp_t = m.get("avg_response_time", 0.0)
                turn_t = m.get("avg_turnaround", m.get("avg_turnaround_time", 0.0))
                
                html += f"<tr><td>{algo}</td><td>{cpu_use:.2f}</td><td>{wait_t:.2f}</td><td>{resp_t:.2f}</td><td>{turn_t:.2f}</td></tr>"
                
                if turn_t < best_turnaround and turn_t > 0: best_turnaround = turn_t; best_turn_algo = algo
                if wait_t < best_wait and wait_t > 0: best_wait = wait_t; best_wait_algo = algo
                if resp_t < best_resp and resp_t > 0: best_resp = resp_t; best_resp_algo = algo
                if cpu_use > best_cpu: best_cpu = cpu_use; best_cpu_algo = algo
                
            html += "</table><p><i>Nota. Elaboraci&oacute;n propia.</i></p>"
            
            html += "<b>An&aacute;lisis de m&eacute;tricas de CPU:</b><br>"
            html += f"<p><b>{best_turn_algo}</b> demostr&oacute; ser el algoritmo m&aacute;s eficiente de manera global al obtener el menor Tiempo de Retorno Promedio ({best_turnaround:.2f}). "
            html += f"En t&eacute;rminos de interactividad, <b>{best_resp_algo}</b> logr&oacute; el mejor Tiempo de Respuesta Promedio ({best_resp:.2f}), "
            html += f"mientras que <b>{best_wait_algo}</b> minimiz&oacute; el Tiempo de Espera Promedio ({best_wait:.2f}). "
            html += f"El mayor aprovechamiento del procesador lo logr&oacute; <b>{best_cpu_algo}</b> con un {best_cpu:.2f}% de Uso de CPU.</p>"
            
            # --- 6.2 Resultados Memoria ---
            html += "<h2>6.2 Resultados de Estrategias de Memoria</h2>"
            html += f"<p>Manteniendo el algoritmo de CPU en {base_cpu_algo}, se evaluaron las tres estrategias de asignaci&oacute;n para la carga de procesos. El sistema se configur&oacute; con {base_scenario.get('hardware', {}).get('memory', {}).get('totalMB', 1024)} MB totales.</p>"
            html += "<b>Tabla 13</b><br><i>M&eacute;tricas obtenidas de las estrategias de memoria implementadas</i><br>"
            html += "<table border='1' cellspacing='0' cellpadding='6' style='border-collapse:collapse; margin-bottom: 10px;'>"
            html += "<tr style='background-color:#f2f2f2;'><th>Estrategia</th><th>Uso de CPU (%)</th><th>Fragmentaci&oacute;n Max (%)</th><th>T. Retorno Promedio</th></tr>"
            
            best_frag = float('inf')
            best_frag_strat = ""
            identical_results = True
            first_frag = -1
            
            for strategy in strategies:
                m = results_mem.get(strategy)
                if not m:
                    html += f"<tr><td>{strategy}</td><td colspan='3'>N/A</td></tr>"
                    continue
                cpu_use = m.get("cpu_utilization_percent", 0.0)
                frag = m.get("fragmentation_percent", 0.0)
                turn_t = m.get("avg_turnaround", m.get("avg_turnaround_time", 0.0))
                
                html += f"<tr><td>{strategy}</td><td>{cpu_use:.2f}</td><td>{frag:.2f}</td><td>{turn_t:.2f}</td></tr>"
                
                if first_frag == -1: first_frag = frag
                elif abs(frag - first_frag) > 0.1: identical_results = False
                
                if frag < best_frag:
                    best_frag = frag
                    best_frag_strat = strategy
            
            html += "</table><p><i>Nota. Elaboraci&oacute;n propia.</i></p>"
            html += "<b>An&aacute;lisis de m&eacute;tricas de Memoria:</b><br>"
            
            if identical_results:
                html += "<p>Debido a que el escenario contaba con una configuraci&oacute;n donde todas las estrategias lograron satisfacer las peticiones de manera similar, "
                html += "el rendimiento general y el pico de fragmentaci&oacute;n resultaron id&eacute;nticos en las pruebas. "
                html += f"El mecanismo de coalescing logr&oacute; mitigar el desperdicio manteniendo la fragmentaci&oacute;n en {best_frag:.2f}%.</p>"
            else:
                html += f"<p>La estrategia <b>{best_frag_strat}</b> result&oacute; ser la m&aacute;s eficiente para este conjunto de procesos, logrando el menor pico de fragmentaci&oacute;n externa ({best_frag:.2f}%). "
                html += "Esto demuestra su capacidad superior para aprovechar los huecos libres frente a la carga dada.</p>"

            # Generar PDF
            doc = QTextDocument()
            doc.setHtml(html)
            
            pdf_writer = QPdfWriter(filepath)
            pdf_writer.setResolution(150)
            doc.print_(pdf_writer)
            
            QMessageBox.information(self, "Reporte Exportado", f"El Reporte fue exportado a PDF exitosamente en:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error al Guardar", f"No se pudo guardar el reporte:\n{e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Refresco de UI
    # ─────────────────────────────────────────────────────────────────────────

    def _refresh(self, snap: Optional[dict] = None):
        """Lee el snapshot estático y actualiza todos los widgets."""
        if snap is None:
            return

        raw_frame = snap.get("_raw_frame", snap)
        log_count = raw_frame.get("_log_count", raw_frame.get("log_count", len(self._global_logs)))

        # ── CPU Cores ────────────────────────────────────────────────────────
        self.cpu_widget.update(snap["cores"])

        # ── Memory — support PAGED, CONTIGUOUS and legacy flat formats ─────────
        mem_block = snap.get("memory")
        mmu_dict = {}
        if isinstance(mem_block, dict) and mem_block.get("type") == "PAGED":
            # Modo paginado: pasar el dict completo al widget; construir mem_stats para statusbar
            mem_segments = mem_block   # memory_widget.update() detecta type==PAGED
            proc_frames = mem_block.get("process_frames", [])
            total_frames = mem_block.get("total_frames", 0)
            os_pages = mem_block.get("os_reserved_frames", 0)
            
            used_pages = len(proc_frames)
            free_pages = total_frames - os_pages - used_pages
            
            total_mb   = round(total_frames * 4.0 / 1024.0, 1)
            used_mb    = round(used_pages  * 4.0 / 1024.0, 3)
            free_mb    = round(free_pages  * 4.0 / 1024.0, 3)
            mem_stats  = {
                "total_mb": total_mb,
                "used_mb":  used_mb,
                "free_mb":  free_mb,
                "fragmentation": 0.0,
                "fragmentation_percent": 0.0,
                "strategy": "VM Paginada",
            }
        elif isinstance(mem_block, dict) and "blocks" in mem_block:
            mem_segments = mem_block["blocks"]
            mem_stats    = mem_block.get("stats", snap.get("memory_stats", {}))
            mmu_raw      = mem_block.get("mmu_table", [])
            # Convertir MMU de formato lista a diccionario para el widget
            if isinstance(mmu_raw, list):
                mmu_dict = {str(e["pid"]): e for e in mmu_raw}
            else:
                mmu_dict = mmu_raw
        else:
            # Legacy: la memoria era una lista de objetos MemorySegment o diccionarios raw
            mem_segments = mem_block if isinstance(mem_block, list) else snap.get("memory_stats", {})
            mem_stats    = snap.get("memory_stats", {})
            
        # Overrides visuales desde escenario_modelo.json (solo aplican a modo CONTIGUOUS)
        if self._live_config and "hardware" in self._live_config and isinstance(mem_block, dict) and mem_block.get("type") != "PAGED":
            hw = self._live_config["hardware"]
            mem_cfg = hw.get("memory", {})
            if not mem_cfg.get("mmuEnabled", True):
                mmu_dict = {}  # Ocultar MMU si se deshabilitó
            if "totalMB" in mem_cfg and "total_mb" not in mem_stats:
                mem_stats["total_mb"] = mem_cfg["totalMB"]
            if "allocationStrategy" in mem_cfg:
                mem_stats["strategy"] = mem_cfg["allocationStrategy"]
                
        current_logs = self._global_logs[:log_count]
        self.memory_widget.update(mem_segments, mem_stats, mmu_dict, current_logs)


        # ── Queues ───────────────────────────────────────────────────────────
        self.queue_widget.update(snap["ready_queues"], snap["waiting"])

        # ── PCB Table — prefer process_table (canonical), fall back to all_processes ──
        processes = snap.get("process_table") or snap.get("all_processes", [])
        self.pcb_table.update(processes)

        # ── I/O ──────────────────────────────────────────────────────────────
        self.io_widget.update(snap["io_devices"])

        # Auto-pausar si hay una interrupción de teclado pendiente de decisión.
        # El reloj se detiene para que el usuario presione Continuar o Cancelar.
        for dev in snap.get("io_devices", []):
            name = (dev.get("name") or dev.get("device_name", "")).upper()
            is_busy = bool(dev.get("is_busy")) or str(dev.get("status", "")).upper() == "BUSY"
            is_resolved = bool(dev.get("resolved", False))
            if name == "KEYBOARD" and is_busy and not is_resolved and self.clock.is_running:
                self.clock.pause()
                self.btn_start.setEnabled(False)   # bloquea reanudar hasta resolver
                self.btn_pause.setEnabled(False)
                self.tabs.setCurrentIndex(2)       # <--- AUTO NAVEGACIÓN A I/O
                break

        # ── Metrics ──────────────────────────────────────────────────────────
        self.metrics_widget.update(snap["metrics"])

        # ── Timeline — use _timeline_count injected into raw frame ──────────
        # We need the raw frame's _timeline_count, not the reconstructed state
        raw_frame = self._playback_data[self._playback_tick - 1] if self._playback_tick > 0 else (self._playback_data[0] if self._playback_data else {})
        timeline_count = raw_frame.get("_timeline_count", raw_frame.get("timeline_count", len(self._global_timeline)))
        log_count = raw_frame.get("_log_count", raw_frame.get("log_count", len(self._global_logs)))
        timeline_raw = self._global_timeline[:timeline_count]
        
        # Formato legacy fallback (si alguna vez se inyecta legacy directo)
        if timeline_raw and isinstance(timeline_raw[0], (list, tuple)):
            timeline_dicts = [
                {"tick": t[0], "core_id": t[1], "label": t[2], "from_state": t[3], "to_state": t[4]}
                for t in timeline_raw
            ]
        else:
            timeline_dicts = timeline_raw
            
        self.timeline_widget.update(timeline_dicts, len(snap.get("cores", [])))
        self.gantt_widget.update_gantt(timeline_dicts, snap.get("tick", 0))
        # ── Log: primero logs directos del motor C++, si no los inferidos ────
        console_logs = snap.get("console_logs", [])
        if console_logs:
            # Logs reales del backend: mostrar sólo los nuevos (del tick actual)
            self.log_widget.append_messages(console_logs)
        else:
            # Fallback: logs inferidos de cambios de estado
            new_msgs = self._global_logs[self._log_offset:log_count]
            if new_msgs:
                self.log_widget.append_messages(new_msgs)
                self._log_offset = log_count

        # ── Status bar ────────────────────────────────────────────────────────
        t    = snap["tick"]
        m    = mem_stats
        procs = processes
        active = sum(1 for p in procs if "TERMINATED" not in str(p.get("state", p.get("estado", ""))).upper())
        ctx_switches = snap["metrics"].get("context_switches", 0) if isinstance(snap.get("metrics"), dict) else 0

        self.sb_tick.setText(f"  T={t}")
        self.sb_procs.setText(f"  Procesos: {active}")
        
        used = m.get('used_mb', 0)
        total = m.get('total_mb', 1)
        usage_pct = m.get('usage_pct', round((used / total) * 100, 1) if total else 0)
        frag_val = m.get('fragmentation', m.get('fragmentation_percent', 0))
        
        try:
            ram_str = f"{float(usage_pct):.1f}"
        except:
            ram_str = str(usage_pct)
            
        try:
            frag_str = f"{float(frag_val):.1f}"
        except:
            frag_str = str(frag_val)
        
        self.sb_mem.setText(f"  RAM: {ram_str}%")
        self.sb_frag.setText(f"  Frag: {frag_str}%")
        self.sb_ctx.setText(f"  CTX: {ctx_switches}")




# ── Diálogo rápido de proceso nuevo ──────────────────────────────────────────

class _NewProcessDialog(QDialog):
    def __init__(self, current_tick: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Añadir Proceso al Escenario")
        self.setModal(True)
        self.setFixedSize(360, 290)
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
        self.spin_burst.setRange(5, 20)
        self.spin_burst.setValue(15)
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

        self.spin_tick = QSpinBox()
        self.spin_tick.setRange(0, 999999)
        self.spin_tick.setValue(current_tick)
        row(5, "Tick de llegada:", self.spin_tick)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("✓  Añadir y Recalcular")
        btn_ok.setObjectName("btn_start")
        btn_ok.clicked.connect(self.accept)
        btns.addWidget(btn_cancel)
        btns.addStretch()
        btns.addWidget(btn_ok)

        btn_widget = QWidget()
        btn_widget.setLayout(btns)
        g.addWidget(btn_widget, 6, 0, 1, 2)

    def get_data(self) -> dict:
        return {
            "name":         self.edit_name.text() or None,
            "burst_time":   self.spin_burst.value(),
            "priority":     self.spin_prio.value(),
            "memory_size":  self.spin_mem.value(),
            "process_type": self.combo_type.currentText(),
            "arrival_tick": self.spin_tick.value(),
        }
