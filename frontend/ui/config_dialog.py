"""
ui/config_dialog.py — Configuración de Hardware v2.

Diálogo de configuración inicial completo (req2.txt).
Organizado en pestañas:
    1. CPU         — cores, scheduler, quantum, context switch, preemptive
    2. Memoria     — total MB, min segmento, estrategia, MMU
    3. Dispositivos— latencias individuales de los 5 dispositivos
    4. Simulación  — velocidad, aging, probabilidades, distribución
    5. Procesos    — modo (sistema/manual), cantidad, distribución

Cada parámetro afecta REALMENTE la simulación (req2.txt).
Al aceptar, retorna un HardwareConfig completo.
"""
from __future__ import annotations

from typing import List, Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QSlider, QCheckBox, QGroupBox, QTabWidget, QWidget,
    QLineEdit, QScrollArea, QFrame, QMessageBox,
)

from simulation.config import HardwareConfig
from .styles import Colors, get_main_stylesheet
import time


def _lbl(text: str, color: str = Colors.TEXT_SEC, size: int = 9) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(f"color:{color}; font-size:{size}pt; background:transparent;")
    return l


def _hint(text: str) -> QLabel:
    l = QLabel(f"💡 {text}")
    l.setWordWrap(True)
    l.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:8pt; background:transparent;")
    return l


class ManualProcessRow(QWidget):
    def __init__(self, idx: int, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        layout.addWidget(_lbl(f"P{idx}:", Colors.ACCENT_LIGHT))

        self.name_edit = QLineEdit(f"Proceso-{idx}")
        self.name_edit.setFixedWidth(110)
        layout.addWidget(self.name_edit)

        self.burst = QSpinBox()
        self.burst.setRange(3, 100)
        self.burst.setValue(20)
        self.burst.setFixedWidth(80)
        layout.addWidget(self.burst)

        self.priority = QSpinBox()
        self.priority.setRange(0, 9)
        self.priority.setValue(5)
        self.priority.setFixedWidth(70)
        layout.addWidget(self.priority)

        self.memory = QSpinBox()
        self.memory.setRange(4, 256)
        self.memory.setValue(32)
        self.memory.setFixedWidth(80)
        layout.addWidget(self.memory)

        self.ptype = QComboBox()
        self.ptype.addItems(["CPU_BOUND", "IO_BOUND", "INTERACTIVE", "SYSTEM"])
        self.ptype.setFixedWidth(120)
        layout.addWidget(self.ptype)

        layout.addStretch()

    def get_data(self) -> dict:
        return {
            "name":         self.name_edit.text() or None,
            "burst_time":   self.burst.value(),
            "priority":     self.priority.value(),
            "memory_size":  self.memory.value(),
            "process_type": self.ptype.currentText(),
        }


class ConfigDialog(QDialog):
    """Diálogo de configuración de hardware inicial."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🥔  PatatOS — Configuración de Hardware")
        self.setModal(True)
        self.setMinimumSize(680, 580)
        self.setStyleSheet(get_main_stylesheet())

        self._manual_rows: List[ManualProcessRow] = []
        self._setup_ui()
        # Inicializar el label de memoria correctamente
        self._update_mem_label(self.spin_mem.value())

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 12)

        # Título
        title = QLabel("🥔  PatatOS  —  Simulador de Sistema Operativo")
        title.setStyleSheet(f"color:{Colors.ACCENT_LIGHT}; font-size:14pt; font-weight:bold; background:transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        sub = _lbl("Configura el hardware antes de iniciar la simulación", Colors.TEXT_SEC, 9)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(sub)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{Colors.BORDER};")
        root.addWidget(sep)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_cpu(),        "🖥️  CPU")
        self.tabs.addTab(self._tab_memory(),     "🧠  Memoria")
        self.tabs.addTab(self._tab_devices(),    "⚙️  Dispositivos")
        self.tabs.addTab(self._tab_simulation(), "⚗️  Simulación")
        self.tabs.addTab(self._tab_processes(),  "📦  Procesos")
        root.addWidget(self.tabs, stretch=1)

        # Botones
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("✕  Cancelar")
        btn_cancel.setObjectName("btn_reset")
        btn_cancel.clicked.connect(self.reject)

        btn_defaults = QPushButton("↺  Valores por defecto")
        btn_defaults.clicked.connect(self._reset_defaults)

        btn_export = QPushButton("💾  Solo Exportar Escenario")
        btn_export.clicked.connect(self._export_json_only)

        btn_start = QPushButton("▶  Generar y Visualizar")
        btn_start.setObjectName("btn_start")
        btn_start.setFixedHeight(36)
        btn_start.clicked.connect(self._generate_and_view)

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_defaults)
        btn_row.addWidget(btn_export)
        btn_row.addStretch()
        btn_row.addWidget(btn_start)
        root.addLayout(btn_row)

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _tab_cpu(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.setSpacing(10)
        g.setContentsMargins(12, 12, 12, 12)

        g.addWidget(_lbl("Número de cores:"), 0, 0)
        self.spin_cores = QSpinBox()
        self.spin_cores.setRange(1, 4)
        self.spin_cores.setValue(1)
        self.spin_cores.setFixedWidth(70)
        g.addWidget(self.spin_cores, 0, 1)
        g.addWidget(_lbl("(1-4 cores independientes, cada uno con su propio scheduler)", Colors.TEXT_MUTED, 8), 0, 2)

        g.addWidget(_lbl("Algoritmo de planificación:"), 1, 0)
        self.combo_sched = QComboBox()
        self.combo_sched.addItems(["FCFS", "SJF", "Round Robin", "Prioridades"])
        self.combo_sched.setFixedWidth(180)
        self.combo_sched.currentIndexChanged.connect(self._on_sched_changed)
        g.addWidget(self.combo_sched, 1, 1)

        g.addWidget(_lbl("Quantum (ticks, para Round Robin):"), 2, 0)
        self.spin_quantum = QSpinBox()
        self.spin_quantum.setRange(1, 50)
        self.spin_quantum.setValue(4)
        self.spin_quantum.setFixedWidth(70)
        self.spin_quantum.setEnabled(False)
        g.addWidget(self.spin_quantum, 2, 1)

        g.addWidget(_lbl("Costo de context switch (ticks):"), 3, 0)
        self.spin_ctx_cost = QSpinBox()
        self.spin_ctx_cost.setRange(0, 10)
        self.spin_ctx_cost.setValue(1)
        self.spin_ctx_cost.setFixedWidth(70)
        g.addWidget(self.spin_ctx_cost, 3, 1)
        g.addWidget(_lbl("0 = instantáneo. Mayor costo → más overhead → menor throughput", Colors.TEXT_MUTED, 8), 3, 2)

        self.chk_preemptive = QCheckBox("Modo apropiativo (permite expulsar procesos en CPU)")
        self.chk_preemptive.setChecked(True)
        g.addWidget(self.chk_preemptive, 4, 0, 1, 3)

        g.addWidget(_hint(
            "FCFS: simple, no preemptivo. SJF: óptimo si se conocen los bursts. "
            "SRTF: apropiativo, mínimo waiting. Priority: con aging anti-starvation. "
            "RR: más justo, configura el quantum. MLFQ: (beta) degradación dinámica."
        ), 5, 0, 1, 3)

        g.setRowStretch(6, 1)
        return w

    def _tab_memory(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.setSpacing(10)
        g.setContentsMargins(12, 12, 12, 12)

        g.addWidget(_lbl("Memoria RAM total (MB):"), 0, 0)
        self.spin_mem = QSpinBox()
        self.spin_mem.setRange(32, 4096)
        self.spin_mem.setValue(1024)
        self.spin_mem.setSingleStep(32)
        self.spin_mem.setFixedWidth(90)
        self.spin_mem.valueChanged.connect(self._update_mem_label)
        g.addWidget(self.spin_mem, 0, 1)

        self.lbl_mem_total = _lbl("", Colors.ACCENT_LIGHT)
        g.addWidget(self.lbl_mem_total, 0, 2)

        # Mode
        self.chk_paged = QCheckBox("Habilitar Modo Paginado (4KB)")
        self.chk_paged.setChecked(False)
        self.chk_paged.toggled.connect(self._on_paged_toggled)
        g.addWidget(self.chk_paged, 1, 0, 1, 3)

        # Contiguous Params Frame
        self.frame_contig = QFrame()
        g_contig = QGridLayout(self.frame_contig)
        g_contig.setContentsMargins(0,0,0,0)
        
        g_contig.addWidget(_lbl("Tamaño mínimo de segmento (MB):"), 0, 0)
        self.spin_min_seg = QSpinBox()
        self.spin_min_seg.setRange(1, 64)
        self.spin_min_seg.setValue(4)
        self.spin_min_seg.setFixedWidth(70)
        g_contig.addWidget(self.spin_min_seg, 0, 1)

        g_contig.addWidget(_lbl("Tamaño máximo de proceso (MB):"), 1, 0)
        self.spin_max_proc = QSpinBox()
        self.spin_max_proc.setRange(8, 1024)
        self.spin_max_proc.setValue(512)
        self.spin_max_proc.setFixedWidth(90)
        g_contig.addWidget(self.spin_max_proc, 1, 1)

        g_contig.addWidget(_lbl("Estrategia de asignación:"), 2, 0)
        self.combo_alloc = QComboBox()
        self.combo_alloc.addItems([
            "First Fit — primer hueco libre suficiente",
            "Best Fit  — hueco más pequeño que alcance",
            "Worst Fit — hueco más grande disponible",
        ])
        self.combo_alloc.setFixedWidth(280)
        g_contig.addWidget(self.combo_alloc, 2, 1, 1, 2)
        
        self.chk_mmu = QCheckBox("Habilitar MMU abstracta (Segmentación)")
        self.chk_mmu.setChecked(True)
        g_contig.addWidget(self.chk_mmu, 3, 0, 1, 3)
        g.addWidget(self.frame_contig, 2, 0, 1, 3)

        # Paged Params Frame
        self.frame_paged = QFrame()
        g_paged = QGridLayout(self.frame_paged)
        g_paged.setContentsMargins(0,0,0,0)
        
        g_paged.addWidget(_lbl("Tipo de Tabla de Páginas:"), 0, 0)
        self.combo_pt = QComboBox()
        self.combo_pt.addItems(["SINGLE_LEVEL", "TWO_LEVEL", "INVERTED", "HASHED"])
        g_paged.addWidget(self.combo_pt, 0, 1)
        
        g_paged.addWidget(_lbl("Algoritmo de Reemplazo:"), 1, 0)
        self.combo_repl = QComboBox()
        self.combo_repl.addItems(["NRU", "FIFO", "SECOND_CHANCE", "CLOCK", "LRU", "NFU", "AGING", "WORKING_SET", "WSCLOCK"])
        g_paged.addWidget(self.combo_repl, 1, 1)
        
        g_paged.addWidget(_lbl("Tipo de Swap:"), 2, 0)
        self.combo_swap_type = QComboBox()
        self.combo_swap_type.addItems(["HDD", "SSD"])
        g_paged.addWidget(self.combo_swap_type, 2, 1)
        
        g_paged.addWidget(_lbl("Tamaño Swap (MB):"), 3, 0)
        self.spin_swap = QSpinBox()
        self.spin_swap.setRange(16, 8192)
        self.spin_swap.setValue(64)
        self.spin_swap.setSingleStep(16)
        g_paged.addWidget(self.spin_swap, 3, 1)
        
        g_paged.addWidget(_lbl("Entradas TLB:"), 4, 0)
        self.spin_tlb = QSpinBox()
        self.spin_tlb.setRange(4, 256)
        self.spin_tlb.setValue(16)
        g_paged.addWidget(self.spin_tlb, 4, 1)
        
        g.addWidget(self.frame_paged, 3, 0, 1, 3)
        self.frame_paged.setVisible(False)

        g.addWidget(_hint(
            "En Modo Contiguo, la memoria se gestiona por bloques y puede haber fragmentación externa. "
            "En Modo Paginado, todo se gestiona en páginas de 4KB con Memoria Virtual y Swap, eliminando la "
            "fragmentación externa e implementando reemplazo de páginas."
        ), 4, 0, 1, 3)

        g.setRowStretch(5, 1)
        return w

    def _tab_devices(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.setSpacing(10)
        g.setContentsMargins(12, 12, 12, 12)

        devices = [
            ("⌨️  KEYBOARD", "keyboard_latency", 7,   "Interacción de usuario (baja latencia)"),
            ("💿  DISK",     "disk_latency",     15,  "Lectura/escritura de archivos"),
            ("🖨️  PRINTER",  "printer_latency",  20,  "Impresión de documentos"),
            ("🌐  NETWORK",  "network_latency",  30,  "Comunicación de red (RTT simulado)"),
            ("🔌  USB",      "usb_latency",      12,  "Transferencia por bus USB"),
        ]
        self._dev_spins: Dict[str, QSpinBox] = {}

        for row, (label, attr, default, desc) in enumerate(devices):
            g.addWidget(_lbl(label, Colors.TEXT_PRIMARY, 10), row, 0)
            spin = QSpinBox()
            spin.setRange(1, 100)
            spin.setValue(default)
            spin.setFixedWidth(70)
            spin.setToolTip(desc)
            g.addWidget(spin, row, 1)
            g.addWidget(_lbl("ticks de servicio"), row, 2)
            g.addWidget(_lbl(desc, Colors.TEXT_MUTED, 8), row, 3)
            self._dev_spins[attr] = spin

        g.addWidget(_hint(
            "La latencia afecta directamente el waiting_time. "
            "Un disco lento (latencia alta) hará que los procesos IO-bound esperen más. "
            "Experimenta cambiando estos valores y observa el cambio en métricas."
        ), len(devices), 0, 1, 4)

        g.setRowStretch(len(devices) + 1, 1)
        return w

    def _tab_simulation(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.setSpacing(10)
        g.setContentsMargins(12, 12, 12, 12)

        # Velocidad
        g.addWidget(_lbl("Velocidad inicial:"), 0, 0)
        speed_row = QHBoxLayout()
        speed_row.addWidget(_lbl("🐌"))
        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(0, 3)
        self.slider_speed.setValue(1)
        self.slider_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_speed.valueChanged.connect(self._update_speed_label)
        speed_row.addWidget(self.slider_speed)
        speed_row.addWidget(_lbl("⚡"))
        speed_w = QWidget()
        speed_w.setLayout(speed_row)
        g.addWidget(speed_w, 0, 1)
        self.lbl_speed = _lbl("Normal (800 ms/tick)", Colors.ACCENT_LIGHT)
        g.addWidget(self.lbl_speed, 0, 2)

        # Probabilidad de error — porcentaje entero
        g.addWidget(_lbl("Probabilidad de error:"), 1, 0)
        err_row = QHBoxLayout()
        self.spin_error_prob = QDoubleSpinBox()
        self.spin_error_prob.setRange(0.0, 50.0)
        self.spin_error_prob.setValue(0.5)        # 0.5 % por defecto (≡ 0.005 decimal)
        self.spin_error_prob.setSingleStep(0.5)
        self.spin_error_prob.setDecimals(1)
        self.spin_error_prob.setFixedWidth(90)
        self.spin_error_prob.setSuffix(" %")
        err_w = QWidget()
        err_w.setLayout(err_row)
        err_row.addWidget(self.spin_error_prob)
        g.addWidget(err_w, 1, 1)
        g.addWidget(_lbl("% de procesos que terminarán con error fatal"), 1, 2)

        # Multiplicador I/O
        g.addWidget(_lbl("Multiplicador de frecuencia I/O:"), 2, 0)
        self.spin_io_mult = QDoubleSpinBox()
        self.spin_io_mult.setRange(0.1, 5.0)
        self.spin_io_mult.setValue(1.0)
        self.spin_io_mult.setSingleStep(0.1)
        self.spin_io_mult.setDecimals(1)
        self.spin_io_mult.setFixedWidth(90)
        g.addWidget(self.spin_io_mult, 2, 1)
        g.addWidget(_lbl("1.0 = base. 2.0 = doble de solicitudes I/O"), 2, 2)

        # Aging
        self.chk_aging = QCheckBox("Aging anti-starvation habilitado")
        self.chk_aging.setChecked(True)
        g.addWidget(self.chk_aging, 3, 0, 1, 3)

        g.addWidget(_lbl("Intervalo de aging (ticks en READY):"), 4, 0)
        self.spin_aging = QSpinBox()
        self.spin_aging.setRange(5, 100)
        self.spin_aging.setValue(20)
        self.spin_aging.setFixedWidth(70)
        g.addWidget(self.spin_aging, 4, 1)
        g.addWidget(_lbl("Cada N ticks esperando, la prioridad sube 1"), 4, 2)

        # Auto-crear
        self.chk_auto = QCheckBox("Auto-crear procesos durante la simulación")
        self.chk_auto.setChecked(False)
        g.addWidget(self.chk_auto, 5, 0, 1, 3)

        # Max ticks (Solo relevante cuando auto_create está activado.)
        self.max_ticks_row = QWidget()
        mt_layout = QHBoxLayout(self.max_ticks_row)
        mt_layout.setContentsMargins(20, 0, 0, 0)
        mt_layout.setSpacing(8)
        mt_layout.addWidget(_lbl("  Detener creación en tick:"))
        self.spin_max_ticks = QSpinBox()
        self.spin_max_ticks.setRange(0, 10000)
        self.spin_max_ticks.setValue(500)
        self.spin_max_ticks.setFixedWidth(90)
        self.spin_max_ticks.setSpecialValueText("Sin límite")
        mt_layout.addWidget(self.spin_max_ticks)
        mt_layout.addWidget(_lbl("  (0 = sin límite; la simulación acaba cuando terminan todos los procesos)",
                                 Colors.TEXT_MUTED, 8))
        mt_layout.addStretch()
        g.addWidget(self.max_ticks_row, 6, 0, 1, 3)
        self.max_ticks_row.setEnabled(False)
        self.chk_auto.toggled.connect(self.max_ticks_row.setEnabled)

        g.addWidget(_hint(
            "El aging evita starvation: procesos que esperan mucho ganan prioridad. "
            "Con quantum pequeño, habrá más context switches y mejor tiempo de respuesta. "
            "Si auto-crear está activo, define un límite de ticks para que la simulación pueda terminar."
        ), 7, 0, 1, 3)

        g.setRowStretch(8, 1)
        return w

    def _tab_processes(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # Radio
        radio_row = QHBoxLayout()
        from PySide6.QtWidgets import QRadioButton, QButtonGroup
        self.radio_sys = QRadioButton("Cargar desde el SO real (psutil)")
        self.radio_manual = QRadioButton("Ingresar manualmente")
        self.radio_sys.setChecked(True)
        self._proc_group = QButtonGroup()
        self._proc_group.addButton(self.radio_sys, 0)
        self._proc_group.addButton(self.radio_manual, 1)
        radio_row.addWidget(self.radio_sys)
        radio_row.addStretch()
        radio_row.addWidget(self.radio_manual)
        outer.addLayout(radio_row)

        # Modo sistema
        self.sys_widget = QWidget()
        sys_layout = QHBoxLayout(self.sys_widget)
        sys_layout.setContentsMargins(0, 0, 0, 0)
        sys_layout.addWidget(_lbl("Cantidad de procesos:"))
        self.spin_proc_count = QSpinBox()
        self.spin_proc_count.setRange(1, 30)
        self.spin_proc_count.setValue(20)
        self.spin_proc_count.setFixedWidth(100)
        sys_layout.addWidget(self.spin_proc_count)

        sys_layout.addWidget(_lbl("  CPU-bound %:"))
        self.spin_cpu_ratio = QSpinBox()
        self.spin_cpu_ratio.setRange(0, 100)
        self.spin_cpu_ratio.setValue(40)
        self.spin_cpu_ratio.setFixedWidth(100)
        sys_layout.addWidget(self.spin_cpu_ratio)
        sys_layout.addWidget(_lbl("  (resto: IO/INTERACTIVE/SYSTEM)"))
        sys_layout.addStretch()
        outer.addWidget(self.sys_widget)

        # Modo manual
        self.manual_widget = QWidget()
        man_layout = QVBoxLayout(self.manual_widget)
        man_layout.setContentsMargins(0, 0, 0, 0)
        man_layout.setSpacing(4)

        header_row = QHBoxLayout()
        for label, width in [("Proceso", 140), ("Burst", 85), ("Prior.", 75), ("Mem (MB)", 85), ("Tipo", 125)]:
            lbl = _lbl(label, Colors.TEXT_SEC, 8)
            lbl.setFixedWidth(width)
            header_row.addWidget(lbl)
        header_row.addStretch()
        man_layout.addLayout(header_row)

        man_scroll = QScrollArea()
        man_scroll.setWidgetResizable(True)
        man_scroll.setFixedHeight(200)
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setSpacing(2)
        self.rows_layout.setContentsMargins(2, 2, 2, 2)
        self._populate_default_manual_rows()
        self.rows_layout.addStretch()
        man_scroll.setWidget(self.rows_container)
        man_layout.addWidget(man_scroll)

        btn_row2 = QHBoxLayout()
        btn_add = QPushButton("＋ Agregar")
        btn_add.setFixedWidth(100)
        btn_add.clicked.connect(self._add_proc_row)
        btn_rem = QPushButton("－ Quitar")
        btn_rem.setFixedWidth(100)
        btn_rem.clicked.connect(self._rem_proc_row)
        btn_row2.addWidget(btn_add)
        btn_row2.addWidget(btn_rem)
        btn_row2.addStretch()
        man_layout.addLayout(btn_row2)

        outer.addWidget(self.manual_widget)
        self.manual_widget.setVisible(False)

        self.radio_sys.toggled.connect(self._toggle_proc_mode)
        self.radio_manual.toggled.connect(self._toggle_proc_mode)

        outer.addStretch()
        return w

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _on_sched_changed(self, idx: int):
        # 0=FCFS, 1=SJF, 2=RR, 3=Priority
        is_rr = (idx == 2)
        self.spin_quantum.setEnabled(is_rr)
        # Auto-configure preemptive: RR y Priority siempre son preemptive.
        if idx in (2, 3):
            self.chk_preemptive.setChecked(True)
            self.chk_preemptive.setEnabled(False)
        else:
            self.chk_preemptive.setEnabled(True)

    def _on_paged_toggled(self, checked: bool):
        self.frame_contig.setVisible(not checked)
        self.frame_paged.setVisible(checked)
        if checked:
            self.spin_mem.setValue(32)
        else:
            self.spin_mem.setValue(1024)

    def _toggle_proc_mode(self):
        sys = self.radio_sys.isChecked()
        self.sys_widget.setVisible(sys)
        self.manual_widget.setVisible(not sys)

    def _update_mem_label(self, val: int):
        # os_reserved = max(8, val // 4)  # 25% reserved for OS, minimum 8 MB
        os_reserved = 64
        avail = val - os_reserved
        self.lbl_mem_total.setText(f"({avail} MB disponibles para procesos)")
        if hasattr(self, 'spin_max_proc'):
            self.spin_max_proc.setMaximum(val)

    def _update_speed_label(self, val: int):
        labels = ["Lento (2000 ms)", "Normal (800 ms)", "Rápido (250 ms)", "Turbo (80 ms)"]
        self.lbl_speed.setText(labels[val])

    # Definiciones de procesos manuales predeterminadas de 20
    _DEFAULT_PROCS = [
        ("Sistema",    10, 0, 48,  "SYSTEM"),
        ("Kernel",      8, 0, 32,  "SYSTEM"),
        ("svchost",    15, 1, 64,  "SYSTEM"),
        ("Explorador", 30, 3, 150, "INTERACTIVE"),
        ("Navegador",  45, 2, 450, "INTERACTIVE"),
        ("Editor",     25, 3, 200, "CPU_BOUND"),
        ("Compilador", 80, 4, 350, "CPU_BOUND"),
        ("Database",   20, 2, 500, "IO_BOUND"),
        ("Servidor",   60, 2, 250, "IO_BOUND"),
        ("Logger",     12, 5, 24,  "IO_BOUND"),
        ("Antivirus",  40, 4, 180, "CPU_BOUND"),
        ("Backup",     90, 6, 120, "IO_BOUND"),
        ("Player",     35, 3, 280, "INTERACTIVE"),
        ("Terminal",   18, 2, 45,  "INTERACTIVE"),
        ("Updater",    50, 7, 85,  "IO_BOUND"),
        ("Scheduler",  10, 1, 16,  "SYSTEM"),
        ("NetworkMgr", 22, 2, 56,  "IO_BOUND"),
        ("UIServer",   28, 3, 110, "INTERACTIVE"),
        ("CryptoSvc",  55, 4, 140, "CPU_BOUND"),
        ("MemMgr",      8, 1, 24,  "SYSTEM"),
    ]

    def _populate_default_manual_rows(self):
        """Pre-populate the manual list with 20 representative default processes."""
        sys_mem = self.spin_mem.value()
        cap = max(4, sys_mem // 4)
        for name, burst, prio, mem, ptype in self._DEFAULT_PROCS:
            row = ManualProcessRow(len(self._manual_rows) + 1)
            row.name_edit.setText(name)
            row.burst.setValue(burst)
            row.priority.setValue(prio)
            row.memory.setValue(min(cap, mem))
            row.ptype.setCurrentText(ptype)
            self._manual_rows.append(row)
            self.rows_layout.insertWidget(self.rows_layout.count(), row)

    def _add_row(self, idx: int):
        row = ManualProcessRow(idx)
        self._manual_rows.append(row)
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)

    def _add_proc_row(self):
        if len(self._manual_rows) < 30:
            self._add_row(len(self._manual_rows) + 1)

    def _rem_proc_row(self):
        if len(self._manual_rows) > 1:
            row = self._manual_rows.pop()
            row.setParent(None)
            row.deleteLater()

    def _reset_defaults(self):
        self.spin_cores.setValue(1)
        self.combo_sched.setCurrentIndex(0)
        self.spin_quantum.setValue(4)
        self.spin_ctx_cost.setValue(1)
        self.chk_preemptive.setChecked(True)
        self.spin_mem.setValue(1024)
        self.chk_paged.setChecked(False)
        self.spin_min_seg.setValue(4)
        self.spin_max_proc.setValue(512)
        self.combo_alloc.setCurrentIndex(0)
        self.chk_mmu.setChecked(True)
        
        self.combo_pt.setCurrentIndex(0)
        self.combo_repl.setCurrentIndex(0)
        self.combo_swap_type.setCurrentIndex(0)
        self.spin_swap.setValue(64)
        self.spin_tlb.setValue(16)
        for attr, spin in self._dev_spins.items():
            defaults = {
                "keyboard_latency": 7, "disk_latency": 15,
                "printer_latency": 20, "network_latency": 30, "usb_latency": 12,
            }
            spin.setValue(defaults.get(attr, 10))
        self.slider_speed.setValue(1)
        self.spin_error_prob.setValue(0.5)   # 0.5 % = 0.005 decimal
        self.spin_io_mult.setValue(1.0)
        self.chk_aging.setChecked(True)
        self.spin_aging.setValue(20)
        self.chk_auto.setChecked(False)
        self.spin_max_ticks.setValue(500)
        self.spin_proc_count.setValue(20)
        self.spin_cpu_ratio.setValue(40)
        self.radio_sys.setChecked(True)
        # Re-populate manual rows with defaults
        for row in self._manual_rows:
            row.setParent(None)
            row.deleteLater()
        self._manual_rows.clear()
        self._populate_default_manual_rows()
        self.rows_layout.addStretch()

    def _on_accept(self):
        if self.radio_manual.isChecked() and len(self._manual_rows) == 0:
            QMessageBox.warning(self, "Sin procesos", "Agrega al menos 1 proceso.")
            return
        self.accept()

    # ── Getter de configuración ───────────────────────────────────────────────

    def get_config(self) -> HardwareConfig:
        """Construye y retorna un HardwareConfig a partir de la UI."""
        speeds = [2000, 800, 250, 80]
        alloc_map = {0: "first", 1: "best", 2: "worst"}
        sched_map = {
            0: "FCFS", 1: "SJF", 2: "RR", 3: "Priority",
        }

        manual_procs = (
            [r.get_data() for r in self._manual_rows]
            if self.radio_manual.isChecked() else []
        )

        return HardwareConfig(
            # CPU
            num_cpus=self.spin_cores.value(),
            quantum_default=self.spin_quantum.value(),
            context_switch_cost=self.spin_ctx_cost.value(),
            scheduler_algorithm=sched_map.get(self.combo_sched.currentIndex(), "FCFS"),
            preemptive=self.chk_preemptive.isChecked(),
            # Memoria
            total_memory_mb=self.spin_mem.value(),
            min_segment_mb=self.spin_min_seg.value(),
            max_process_mb=self.spin_max_proc.value(),
            alloc_strategy=alloc_map.get(self.combo_alloc.currentIndex(), "first"),
            mmu_enabled=self.chk_mmu.isChecked(),
            memory_mode="PAGED" if self.chk_paged.isChecked() else "CONTIGUOUS",
            page_table_type=self.combo_pt.currentText(),
            replacement_algorithm=self.combo_repl.currentText(),
            swap_device_type=self.combo_swap_type.currentText(),
            swap_size_mb=self.spin_swap.value(),
            tlb_size=self.spin_tlb.value(),
            # Dispositivos
            keyboard_latency=self._dev_spins["keyboard_latency"].value(),
            disk_latency=self._dev_spins["disk_latency"].value(),
            printer_latency=self._dev_spins["printer_latency"].value(),
            network_latency=self._dev_spins["network_latency"].value(),
            usb_latency=self._dev_spins["usb_latency"].value(),
            # Simulación
            sim_speed_ms=speeds[self.slider_speed.value()],
            error_probability=self.spin_error_prob.value() / 100.0,  # UI en %, engine en decimal
            io_freq_multiplier=self.spin_io_mult.value(),
            aging_enabled=self.chk_aging.isChecked(),
            aging_interval=self.spin_aging.value(),
            auto_create=self.chk_auto.isChecked(),
            max_ticks=self.spin_max_ticks.value() if self.chk_auto.isChecked() else 0,
            # Procesos
            initial_processes=self.spin_proc_count.value() if self.radio_sys.isChecked() else len(manual_procs),
            cpu_bound_ratio=self.spin_cpu_ratio.value() / 100.0,
            use_system_processes=self.radio_sys.isChecked(),
        ), manual_procs

    def _get_psutil_processes(self, count: int) -> list:
        """Read up to `count` real OS processes via psutil and return as dicts."""
        try:
            import psutil
            procs = []
            for p in psutil.process_iter(['pid', 'name', 'memory_info', 'nice']):
                try:
                    info = p.info
                    if info['memory_info'] is None:
                        continue
                    
                    sys_mem = self.spin_mem.value()
                    cap = max(4, sys_mem // 4)
                    rss_mb = max(4, min(cap, info['memory_info'].rss // (1024 * 1024)))
                    name = (info['name'] or 'proc')[:16]
                    # Heuristic type
                    nl = name.lower()
                    if any(s in nl for s in ('system','kernel','svchost','winlogon','csrss','lsass','smss','wininit','services','registry')):
                        ptype = 'SYSTEM'
                    elif any(s in nl for s in ('chrome','firefox','edge','explorer','vlc','spotify','discord','word','excel')):
                        ptype = 'IO_BOUND'
                    elif any(s in nl for s in ('cmd','powershell','bash','terminal','code','notepad','python')):
                        ptype = 'INTERACTIVE'
                    else:
                        ptype = 'CPU_BOUND'
                    import random
                    
                    nice_val = info.get('nice')
                    # Asignación de prioridad de Windows a PatatOS 0-9 (0=Highest, 9=Lowest)
                    if nice_val == psutil.REALTIME_PRIORITY_CLASS:
                        prio = 0
                    elif nice_val == psutil.HIGH_PRIORITY_CLASS:
                        prio = 2
                    elif nice_val == getattr(psutil, 'ABOVE_NORMAL_PRIORITY_CLASS', 32768):
                        prio = 3
                    elif nice_val == psutil.NORMAL_PRIORITY_CLASS:
                        prio = 5
                    elif nice_val == getattr(psutil, 'BELOW_NORMAL_PRIORITY_CLASS', 16384):
                        prio = 7
                    elif nice_val == psutil.IDLE_PRIORITY_CLASS:
                        prio = 9
                    else:
                        # Fallback heuristic based on ptype if nice is unavailable
                        if ptype == 'SYSTEM': prio = 2
                        elif ptype == 'IO_BOUND': prio = 4
                        elif ptype == 'INTERACTIVE': prio = 3
                        else: prio = 6

                    procs.append({
                        'name': name,
                        'burst_time': random.randint(2, 15),
                        'priority': prio,
                        'memory_size': rss_mb,
                        'process_type': ptype,
                    })
                    if len(procs) >= count:
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return procs
        except ImportError:
            return []

    def _build_scenario_json(self) -> dict:
        import json
        from datetime import datetime
        config, manual_procs = self.get_config()

        # Determinar la lista de procesos para la exportación
        if self.radio_sys.isChecked():
            count = self.spin_proc_count.value()
            proc_list = self._get_psutil_processes(count)
            if not proc_list:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Dependencia faltante", 
                                    "No se pudo cargar la librería 'psutil' (o no devolvió procesos). "
                                    "Se generarán procesos por defecto.\\n\\n"
                                    "Abre tu terminal y ejecuta:\\n"
                                    "pip install psutil")
                sys_mem = self.spin_mem.value()
                cap = max(4, sys_mem // 4)
                proc_list = []
                for name, burst, prio, mem, ptype in self._DEFAULT_PROCS[:count]:
                    scaled_mem = max(4, min(cap, mem))
                    proc_list.append({
                        "name": name, "burst_time": burst, "priority": prio,
                        "memory_size": scaled_mem, "process_type": ptype
                    })
        else:
            proc_list = manual_procs

        import random
        # Hacer que los procesos lleguen casi al mismo tiempo y duren más para forzar Swap
        for i, p in enumerate(proc_list):
            if "arrival_tick" not in p:
                p["arrival_tick"] = random.randint(0, 10)

        now = datetime.now()
        data = {
            "metadata": {
                "name":                    "Simulación OS Completa - Proyecto Final",
                "executionDate":           now.strftime("%Y-%m-%d"),
                "executionTime":           now.strftime("%H:%M:%S"),
                "realTimeTrackingEnabled": False,
                "availableAlgorithms":     ["FCFS", "SJF", "SRTF", "Priority", "RR", "MLFQ"],
                "processSource":           "psutil" if self.radio_sys.isChecked() else "manual",
            },

            "hardware": {
                "cpu": {
                    "numCores":              config.num_cpus,
                    "scheduler":             config.scheduler_algorithm,
                    "preemptive":            config.preemptive,
                    "quantum":               config.quantum_default,
                    "contextSwitchCostTicks":config.context_switch_cost,
                },
                "memory": {
                    "mode":                 config.memory_mode,
                    "totalMB":              config.total_memory_mb,
                    "osReservedMB":         max(8, config.total_memory_mb // 4),
                    "minSegmentMB":         config.min_segment_mb,
                    "maxProcessMB":         config.max_process_mb,
                    "allocationStrategy":   config.alloc_strategy.upper() + "_FIT",
                    "mmuEnabled":           config.mmu_enabled,
                    "pageTableType":        config.page_table_type,
                    "replacementAlgorithm": config.replacement_algorithm,
                    "swapDeviceType":       config.swap_device_type,
                    "swapSizeMB":           config.swap_size_mb,
                    "tlbSize":              config.tlb_size,
                },
                "ioDevices": [
                    {"id": "KEYBOARD", "latency": config.keyboard_latency},
                    {"id": "DISK",     "latency": config.disk_latency},
                    {"id": "PRINTER",  "latency": config.printer_latency},
                    {"id": "NETWORK",  "latency": config.network_latency},
                    {"id": "USB",      "latency": config.usb_latency},
                ],
            },

            "simulation": {
                "speedMS":               config.sim_speed_ms,
                "errorProbabilityPct":   round(config.error_probability * 100, 2),
                "errorProbabilityDecimal": config.error_probability,
                "ioFreqMultiplier":      config.io_freq_multiplier,
                "aging": {
                    "enabled":  config.aging_enabled,
                    "interval": config.aging_interval,
                },
                "autoCreate": {
                    "enabled":  config.auto_create,
                    "maxTicks": config.max_ticks,    # 0 = sin límite
                },
                "cpuBoundRatio":         config.cpu_bound_ratio,
            },

            "processes": proc_list,
        }
        return data

    def _export_json_only(self):
        import json
        from simulation.paths import ESCENARIO_PATH
        data = self._build_scenario_json()
        with open(ESCENARIO_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        n = len(data["processes"])
        src = "del SO real (psutil)" if self.radio_sys.isChecked() else "manuales"
        QMessageBox.information(
            self, "Exportado",
            f"Se generó input.json con {n} procesos {src}."
        )

    def _generate_and_view(self):
        import json
        import subprocess
        import time
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import QCoreApplication
        from simulation.paths import ESCENARIO_PATH, BACKEND_DIR, SIMULATOR_EXE

        if self.radio_manual.isChecked() and len(self._manual_rows) == 0:
            QMessageBox.warning(self, "Sin procesos", "Agrega al menos 1 proceso manual o cambia a modo SO Real.")
            return

        # 1. Save input
        data = self._build_scenario_json()
        with open(ESCENARIO_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # 2. Llamada al Backend de C++
        progress = QProgressDialog("Esperando respuesta del motor C++...", None, 0, 0, self)
        progress.setWindowTitle("Simulando")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None) # No permitir cancelar
        progress.show()
        
        try:
            # Ejecutar de forma no bloqueante para la UI usando Popen
            process = subprocess.Popen([SIMULATOR_EXE, "-t", "50000"], cwd=BACKEND_DIR)
            
            # Polling hasta que termine
            while process.poll() is None:
                QCoreApplication.processEvents()
                time.sleep(0.05)
                
            if process.returncode != 0:
                QMessageBox.critical(self, "Error de Backend", f"El motor C++ terminó con error: {process.returncode}")
                progress.close()
                return
                
        except FileNotFoundError:
             QMessageBox.critical(self, "Error de Backend", f"No se encontró el ejecutable: {SIMULATOR_EXE}")
             progress.close()
             return
        except Exception as e:
            QMessageBox.critical(self, "Error de Backend", f"Fallo al ejecutar el motor C++:\n{e}")
            progress.close()
            return
            
        progress.close()
        
        # 3. Accept dialog (main.py will then open the player)
        self.accept()
