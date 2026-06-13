"""
ui/widgets/io_widget.py — Widget de Estado de Dispositivos I/O.

Muestra cada dispositivo con su estado (IDLE/BUSY), progreso y cola.
El dispositivo KEYBOARD muestra un panel de interrupción cuando está BUSY,
con botones de Cancelar y Continuar para que el usuario resuelva la señal.
"""
from __future__ import annotations
from typing import List, Dict, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QFrame, QPushButton, QSizePolicy, QScrollArea
)

from ui.styles import Colors


class IOStatusWidget(QWidget):
    # Emitida cuando el usuario presiona Cancelar/Continuar en el teclado.
    # Argumentos: pid (int), action (str: "CANCEL" o "CONTINUE")
    keyboard_signal = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._device_rows: Dict[str, _DeviceRow] = {}

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("Dispositivos I/O")
        title.setStyleSheet(f"color: {Colors.ACCENT_LIGHT}; font-weight: bold; font-size: 11pt;")
        layout.addWidget(title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        
        self.container = QVBoxLayout(self.scroll_content)
        self.container.setSpacing(4)
        self.container.setContentsMargins(0, 0, 0, 0)
        self.container.addStretch()

        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll, 1)

    def update(self, devices: List[Dict[str, Any]]):
        # Crear filas si aún no existen (sólo se crean una vez)
        if not self._device_rows:
            for dev in devices:
                name = dev.get("name") or dev.get("device_name", "?")
                is_keyboard = (name.upper() == "KEYBOARD")
                row = _DeviceRow(name, has_keyboard_controls=is_keyboard)
                if is_keyboard:
                    row.cancel_clicked.connect(
                        lambda pid: self.keyboard_signal.emit(pid, "CANCEL"))
                    row.continue_clicked.connect(
                        lambda pid: self.keyboard_signal.emit(pid, "CONTINUE"))
                self._device_rows[name] = row
                # Insertar antes del stretch al final
                self.container.insertWidget(self.container.count() - 1, row)

        for dev in devices:
            name = dev.get("name") or dev.get("device_name", "?")
            if name in self._device_rows:
                self._device_rows[name].update_status(dev)


class _DeviceRow(QFrame):
    cancel_clicked   = Signal(int)
    continue_clicked = Signal(int)

    def __init__(self, name: str, has_keyboard_controls: bool = False, parent=None):
        super().__init__(parent)
        self._current_pid: int = -1
        self._has_kbd = has_keyboard_controls

        # Usar objectName para que el estilo sea sólo para este QFrame
        # y NO se propague a los QLabel hijos
        self.setObjectName("deviceRow")
        self._base_style = "QFrame#deviceRow { background-color: " + Colors.BG_ELEVATED + "; border: 1px solid " + Colors.BORDER + "; border-radius: 6px; }"
        self._interrupt_style = "QFrame#deviceRow { background-color: #2D1500; border: 2px solid " + Colors.STATE_WAITING + "; border-radius: 6px; }"
        self.setStyleSheet(self._base_style)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(5)

        # ── Fila normal (nombre + cola + badge) ──────────────────────────────
        header = QHBoxLayout()
        self.lbl_name = QLabel(name)
        self.lbl_name.setStyleSheet(
            "font-weight: bold; font-size: 9pt; border: none; background: transparent;"
        )

        self.lbl_queue = QLabel("Q: 0")
        self.lbl_queue.setStyleSheet(
            f"color:{Colors.TEXT_SEC}; border:none; background:transparent; font-size:8pt;"
        )

        self.lbl_badge = QLabel("IDLE")
        self.lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_badge.setFixedSize(54, 20)
        self._set_badge(False)

        header.addWidget(self.lbl_name)
        header.addStretch()
        header.addWidget(self.lbl_queue)
        header.addWidget(self.lbl_badge)
        self._layout.addLayout(header)

        # ── Proceso actual ────────────────────────────────────────────────────
        self.lbl_current = QLabel("—")
        self.lbl_current.setStyleSheet(
            f"color:{Colors.TEXT_SEC}; border:none; background:transparent; font-size:8pt;"
        )
        self._layout.addWidget(self.lbl_current)

        # ── Barra de progreso ─────────────────────────────────────────────────
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Colors.BG_BASE};
                border: none; border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {Colors.ACCENT}; border-radius: 2px;
            }}
        """)
        self._layout.addWidget(self.progress)

        # ── Panel de interrupción de teclado (oculto por defecto) ────────────
        if has_keyboard_controls:
            # Separador visual
            self._kbd_separator = QFrame()
            self._kbd_separator.setFrameShape(QFrame.HLine)
            self._kbd_separator.setStyleSheet(f"color:{Colors.STATE_WAITING}88;")
            self._kbd_separator.setVisible(False)
            self._layout.addWidget(self._kbd_separator)

            # Mensaje de interrupción
            self._interrupt_lbl = QLabel()
            self._interrupt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._interrupt_lbl.setWordWrap(True)
            self._interrupt_lbl.setStyleSheet(
                f"color:{Colors.STATE_WAITING}; font-size:8pt; font-weight:bold;"
                f" background:transparent; border:none;"
            )
            self._interrupt_lbl.setVisible(False)
            self._layout.addWidget(self._interrupt_lbl)

            # Botones de decisión
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)

            self.btn_cancel   = QPushButton("✖  Cancelar proceso")
            self.btn_continue = QPushButton("✔  Completar E/S")

            for btn, color in [
                (self.btn_cancel,   "#C0392B"),
                (self.btn_continue, "#27AE60"),
            ]:
                btn.setFixedHeight(28)
                btn.setEnabled(False)
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background:{Colors.BG_BASE}; color:{Colors.TEXT_MUTED};"
                    f"  border:1px solid {Colors.BORDER}; border-radius:5px;"
                    f"  font-size:8pt; font-weight:bold;"
                    f"}}"
                    f"QPushButton:enabled {{"
                    f"  color:#FFFFFF; border-color:{color}; background:{color}33;"
                    f"}}"
                    f"QPushButton:enabled:hover {{"
                    f"  background:{color}66;"
                    f"}}"
                )

            self.btn_cancel.setVisible(False)
            self.btn_continue.setVisible(False)

            self.btn_cancel.clicked.connect(
                lambda: self.cancel_clicked.emit(self._current_pid))
            self.btn_continue.clicked.connect(
                lambda: self.continue_clicked.emit(self._current_pid))

            btn_row.addWidget(self.btn_cancel)
            btn_row.addWidget(self.btn_continue)
            self._kbd_btn_layout = btn_row
            self._layout.addLayout(btn_row)
        else:
            self.btn_cancel   = None
            self.btn_continue = None
            self._kbd_separator = None
            self._interrupt_lbl = None

    # ── Badge helper ──────────────────────────────────────────────────────────

    def _set_badge(self, is_busy: bool):
        if is_busy:
            self.lbl_badge.setText("BUSY")
            self.lbl_badge.setStyleSheet(f"""
                background-color: {Colors.STATE_WAITING}33;
                color: {Colors.STATE_WAITING};
                border-radius: 10px; font-size: 7pt; font-weight: bold;
                border: 1px solid {Colors.STATE_WAITING};
            """)
        else:
            self.lbl_badge.setText("IDLE")
            self.lbl_badge.setStyleSheet(f"""
                background-color: {Colors.BG_BASE};
                color: {Colors.TEXT_MUTED};
                border-radius: 10px; font-size: 7pt; font-weight: bold;
                border: 1px solid {Colors.BORDER};
            """)

    # ── Public update ─────────────────────────────────────────────────────────

    def update_status(self, dev: dict):
        # Soporta is_busy (bool) y status (str)
        if "is_busy" in dev:
            is_busy = bool(dev["is_busy"])
        else:
            is_busy = str(dev.get("status", "IDLE")).upper() == "BUSY"

        self._set_badge(is_busy)
        self.lbl_queue.setText(f"Q: {dev.get('queue_length', 0)}")
        progress = dev.get("progress_percent") or dev.get("progress") or 0

        if is_busy:
            pid  = dev.get("current_pid", -1)
            name = dev.get("current_name", "")
            self._current_pid = int(pid) if pid else -1
            self.lbl_current.setText(f"P{pid} ({name})" if name else f"PID {pid}")
            self.progress.setValue(int(progress))
        else:
            self._current_pid = -1
            self.lbl_current.setText("—")
            self.progress.setValue(0)

        # Mostrar/ocultar panel de interrupción del teclado
        if self._has_kbd:
            if is_busy:
                proc_text = self.lbl_current.text()
                self._interrupt_lbl.setText(
                    f"⚠️  Interrupción de Teclado\n"
                    f"{proc_text} está bloqueado\n"
                    f"¿Qué decide el SO?"
                )
                self._kbd_separator.setVisible(True)
                self._interrupt_lbl.setVisible(True)
                self.btn_cancel.setVisible(True)
                self.btn_continue.setVisible(True)
                self.btn_cancel.setEnabled(True)
                self.btn_continue.setEnabled(True)
                self.setStyleSheet(self._interrupt_style)
            else:
                self._kbd_separator.setVisible(False)
                self._interrupt_lbl.setVisible(False)
                self.btn_cancel.setVisible(False)
                self.btn_continue.setVisible(False)
                self.setStyleSheet(self._base_style)
