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
    QLineEdit, QDoubleSpinBox, QScrollArea, QMenuBar, QSizePolicy
)
from PySide6.QtGui import QAction

from simulation.clock import SimClock
from simulation.config import HardwareConfig
from ui.styles import Colors, get_main_stylesheet
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
        self.output_file = output_file
        
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

        if self._playback_data:
            self._refresh(self._playback_data[0])

    def _load_json(self, filepath: str):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._playback_data = data.get("ticks", [])
        except Exception as e:
            self._playback_data = []

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
        
        self.btn_load_json = QPushButton("📂  Cargar JSON")
        self.btn_load_json.setFixedHeight(30)
        self.btn_load_json.clicked.connect(self._on_load_json)
        tb.addWidget(self.btn_load_json)

        tb.addWidget(_sep())

        # Nuevo proceso
        self.btn_new = QPushButton("＋  Añadir Proceso en Caliente")
        self.btn_new.setFixedHeight(30)
        self.btn_new.clicked.connect(self._on_new_process)
        tb.addWidget(self.btn_new)

        tb.addWidget(_sep())

        # Configuración en caliente
        tb.addWidget(_lbl("  Algoritmo:"))
        self.combo_sched = QComboBox()
        self.combo_sched.addItems(["FCFS", "RoundRobin", "Priority", "Priority-RR"])
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

        # ── Métricas en la parte superior derecha ──
        self.sb_tick    = QLabel("  T=0")
        self.sb_procs   = QLabel("  Procesos: 0")
        self.sb_mem     = QLabel("  RAM: 0%")
        self.sb_frag    = QLabel("  Frag: 0%")
        self.sb_ctx     = QLabel("  CTX: 0")

        for w in [self.sb_tick, QLabel(" | "),
                  self.sb_procs, QLabel(" | "), self.sb_mem, QLabel(" | "),
                  self.sb_frag, QLabel(" | "), self.sb_ctx]:
            tb.addWidget(w)

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

        # Detect num cores from snapshot if available, else 1
        num_c = 1
        if self._playback_data and "cores" in self._playback_data[0]:
            num_c = len(self._playback_data[0]["cores"])

        self.cpu_widget = CPUWidget(num_cores=num_c)
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
                self._refresh(self._playback_data[0])


    def _on_speed(self, idx: int):
        from PySide6.QtWidgets import QInputDialog
        speeds = [SimClock.SPEED_SLOW, SimClock.SPEED_NORMAL,
                  SimClock.SPEED_FAST, SimClock.SPEED_TURBO]
        if idx < 4:
            self.clock.set_speed(speeds[idx])
        else:
            val, ok = QInputDialog.getInt(self, "Velocidad Personalizada", "Milisegundos por tick (ms/t):", 
                                          self.clock._speed_ms, 10, 10000, 10)
            if ok:
                self.clock.set_speed(val)
            else:
                self.combo_speed.blockSignals(True)
                self.combo_speed.setCurrentIndex(1)
                self.combo_speed.blockSignals(False)
                self.clock.set_speed(speeds[1])

    def _sync_config_from_file(self):
        if not os.path.exists("escenario_modelo.json"):
            return
        try:
            with open("escenario_modelo.json", "r", encoding="utf-8") as f:
                scen = json.load(f)
            
            algo = scen.get("hardware", {}).get("algorithm", "FCFS")
            q = scen.get("hardware", {}).get("quantum", 4)
            mem = scen.get("hardware", {}).get("memory_strategy", "FirstFit")
            
            idx_sched = self.combo_sched.findText(algo)
            if idx_sched >= 0: self.combo_sched.setCurrentIndex(idx_sched)
            self.spin_q.setValue(q)
            idx_mem = self.combo_mem.findText(mem)
            if idx_mem >= 0: self.combo_mem.setCurrentIndex(idx_mem)
        except Exception:
            pass

    def _on_hot_config_change(self):
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import QCoreApplication

        if not os.path.exists("escenario_modelo.json"):
            return
            
        was_running = self.clock.is_running
        self.clock.pause()
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        
        try:
            with open("escenario_modelo.json", "r", encoding="utf-8") as f:
                scen = json.load(f)
                
            if "hardware" not in scen:
                scen["hardware"] = {}
                
            scen["hardware"]["algorithm"] = self.combo_sched.currentText()
            scen["hardware"]["quantum"] = self.spin_q.value()
            scen["hardware"]["memory_strategy"] = self.combo_mem.currentText()
            
            with open("escenario_modelo.json", "w", encoding="utf-8") as f:
                json.dump(scen, f, indent=4)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al guardar JSON: {e}")
            return
            
        # Llamada al Backend de C++ para Recalcular (PENDIENTE)
        # TODO(Backend C++): Descomentar estas líneas cuando el motor C++ pueda
        # leer el escenario modificado y generar un nuevo output_modelo.json
        # import subprocess
        # try:
        #     subprocess.run(["engine.exe", "escenario_modelo.json"], check=True)
        # except Exception as e:
        #     QMessageBox.critical(self, "Error de Backend", f"Fallo al ejecutar el motor C++:\n{e}")
        #     return
            
        # --- SIMULACIÓN TEMPORAL DE CARGA (Borrar cuando haya backend real) ---
        pd = QProgressDialog("Recalculando Universo en el Backend (C++)...", None, 0, 100, self)
        pd.setWindowTitle("Aplicando Configuración...")
        pd.setWindowModality(Qt.WindowModality.WindowModal)
        pd.setMinimumDuration(0)
        pd.setValue(0)

        for i in range(101):
            pd.setValue(i)
            QCoreApplication.processEvents()
            time.sleep(0.015)
            
        # Reload current output
        try:
            with open(self.output_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            self._playback_data = d.get("ticks", [])
        except:
            pass
            
        self._playback_tick = min(self._playback_tick, len(self._playback_data) - 1) if self._playback_data else 0
        
        if self._playback_data and self._playback_tick >= 0:
            self._refresh(self._playback_data[self._playback_tick])

        if was_running:
            self._on_start()

    def _on_new_process(self):
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import QCoreApplication

        self.clock.pause()
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)

        dlg = _NewProcessDialog(self._playback_tick, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.get_data()
            
            # Read input scenario
            if os.path.exists("escenario_modelo.json"):
                with open("escenario_modelo.json", "r", encoding="utf-8") as f:
                    scen = json.load(f)
            else:
                scen = {"processes": []}
            
            # Append new process
            scen["processes"].append(d)
            
            # Save input scenario
            with open("escenario_modelo.json", "w", encoding="utf-8") as f:
                json.dump(scen, f, indent=2, ensure_ascii=False)
            
            # 1. Llamada al Backend de C++ para Recalcular (PENDIENTE)
            # TODO(Backend C++): Descomentar estas líneas cuando el motor C++ esté listo.
            # import subprocess
            # try:
            #     subprocess.run(["engine.exe", "escenario_modelo.json"], check=True)
            # except Exception as e:
            #     QMessageBox.critical(self, "Error de Backend", f"Fallo al ejecutar el motor C++:\n{e}")
            #     return

            # --- SIMULACIÓN TEMPORAL DE CARGA (Borrar cuando haya backend real) ---
            progress = QProgressDialog("Recalculando el futuro en el backend (C++)...", None, 0, 100, self)
            progress.setWindowTitle("Generando Output")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()

            for i in range(101):
                progress.setValue(i)
                QCoreApplication.processEvents()
                time.sleep(0.015)  # Total 1.5s delay
            
            progress.close()

            # Note: For the actual C++ backend, we would reload output_modelo.json here.
            # Since this is a mockup and we don't have C++, we just resume.
            self._load_json(self.output_file)
            
            QMessageBox.information(self, "Recálculo Completo", f"El backend simuló el nuevo universo a partir del tick {d['arrival_tick']}. La animación continuará desde ese punto.")
            
            # Resume exactly where we paused
            if self._playback_tick < len(self._playback_data):
                self._refresh(self._playback_data[self._playback_tick])
            self._on_start()

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
                
            self._playback_data = data["ticks"]
            self._playback_mode = True
            self._playback_tick = 0
            
            # Disable engine controls
            self.btn_new.setEnabled(False)
            self.combo_sched.setEnabled(False)
            self.spin_q.setEnabled(False)
            self.combo_mem.setEnabled(False)
            
            self.setWindowTitle(f"🥔  PatatOS — REPRODUCIENDO: {os.path.basename(filepath)}")
            QMessageBox.information(self, "Cargado", f"Se cargaron {len(self._playback_data)} fotogramas de simulación. Presiona Iniciar para reproducir.")
            
            # Show tick 0
            self._refresh(self._playback_data[0])
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al cargar el archivo:\n{e}")

    def _on_tick(self, tick: int):
        """Callback del clock: avanzar un fotograma en la reproducción."""
        if self._playback_mode and self._playback_data:
            if self._playback_tick < len(self._playback_data):
                snap = self._playback_data[self._playback_tick]
                self._refresh(snap)
                self._playback_tick += 1
            else:
                self._on_pause()

    # ─────────────────────────────────────────────────────────────────────────
    # Refresco de UI
    # ─────────────────────────────────────────────────────────────────────────

    def _refresh(self, snap: Optional[dict] = None):
        """Lee el snapshot estático y actualiza todos los widgets."""
        if snap is None:
            return

        # ── CPU Cores ────────────────────────────────────────────────────────
        self.cpu_widget.update(snap["cores"])

        # ── Memory — support both new nested format and legacy flat format ───
        mem_block = snap.get("memory")
        if isinstance(mem_block, dict) and "blocks" in mem_block:
            mem_segments = mem_block["blocks"]
            mem_stats    = mem_block.get("stats", snap.get("memory_stats", {}))
            mmu_raw      = mem_block.get("mmu_table", [])
            # Convert list-of-entries MMU to dict for the widget
            if isinstance(mmu_raw, list):
                mmu_dict = {str(e["pid"]): e for e in mmu_raw}
            else:
                mmu_dict = mmu_raw
        else:
            # Legacy: memory was a list of MemorySegment objects or raw dicts
            mem_segments = mem_block if isinstance(mem_block, list) else snap.get("memory_stats", {})
            mem_stats    = snap.get("memory_stats", {})
            mmu_dict     = snap.get("mmu_table", {})
        self.memory_widget.update(mem_segments, mem_stats, mmu_dict)

        # ── Queues ───────────────────────────────────────────────────────────
        self.queue_widget.update(snap["ready_queues"], snap["waiting"])

        # ── PCB Table — prefer process_table (canonical), fall back to all_processes ──
        processes = snap.get("process_table") or snap.get("all_processes", [])
        self.pcb_table.update(processes)

        # ── I/O ──────────────────────────────────────────────────────────────
        self.io_widget.update(snap["io_devices"])

        # ── Metrics ──────────────────────────────────────────────────────────
        self.metrics_widget.update(snap["metrics"])

        # ── Timeline — support both list-of-dicts (new) and list-of-tuples (legacy) ──
        timeline_raw = snap.get("timeline", [])
        if timeline_raw and isinstance(timeline_raw[0], (list, tuple)):
            # Legacy tuple format: (tick, core_id, label, from_state, to_state)
            timeline_dicts = [
                {"tick": t[0], "core_id": t[1], "label": t[2], "from_state": t[3], "to_state": t[4]}
                for t in timeline_raw
            ]
        else:
            timeline_dicts = timeline_raw
        self.timeline_widget.update(timeline_dicts, len(snap["cores"]))

        # ── Log incremental ───────────────────────────────────────────────────
        log_key = "console_logs" if "console_logs" in snap else "log"
        log_list = snap.get(log_key, [])
        new_msgs = log_list[self._log_offset:]
        if new_msgs:
            self.log_widget.append_messages(new_msgs)
            self._log_offset = len(log_list)

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
        
        self.sb_mem.setText(f"  RAM: {usage_pct}%")
        self.sb_frag.setText(f"  Frag: {m.get('fragmentation', m.get('fragmentation_percent', 0))}%")
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
