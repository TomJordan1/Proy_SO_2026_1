"""
ui/widgets/io_widget.py — Widget de Estado de Dispositivos I/O.
"""
from __future__ import annotations
from typing import List, Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame
)

from ui.styles import Colors

class IOStatusWidget(QWidget):
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

        self.container = QVBoxLayout()
        self.container.setSpacing(4)
        layout.addLayout(self.container)
        layout.addStretch()

    def update(self, devices: List[Dict[str, Any]]):
        # Create rows if not exist
        if not self._device_rows:
            for dev in devices:
                name = dev.get("name") or dev.get("device_name", "?")
                row = _DeviceRow(name)
                self._device_rows[name] = row
                self.container.addWidget(row)

        for dev in devices:
            name = dev.get("name") or dev.get("device_name", "?")
            if name in self._device_rows:
                self._device_rows[name].update_status(dev)

class _DeviceRow(QFrame):
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        self.lbl_name = QLabel(name)
        self.lbl_name.setStyleSheet(f"font-weight: bold; border: none; background: transparent;")
        
        self.lbl_badge = QLabel("IDLE")
        self.lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_badge.setFixedSize(50, 18)
        self._set_badge(False)

        self.lbl_queue = QLabel("Q: 0")
        self.lbl_queue.setStyleSheet("color: " + Colors.TEXT_SEC + "; border: none; background: transparent; font-size: 8pt;")

        header.addWidget(self.lbl_name)
        header.addStretch()
        header.addWidget(self.lbl_queue)
        header.addWidget(self.lbl_badge)
        layout.addLayout(header)

        self.lbl_current = QLabel("—")
        self.lbl_current.setStyleSheet("color: " + Colors.TEXT_SEC + "; border: none; background: transparent; font-size: 8pt;")
        layout.addWidget(self.lbl_current)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Colors.BG_BASE};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {Colors.ACCENT};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.progress)

    def _set_badge(self, is_busy: bool):
        if is_busy:
            self.lbl_badge.setText("BUSY")
            self.lbl_badge.setStyleSheet(f"""
                background-color: {Colors.STATE_WAITING}40;
                color: {Colors.STATE_WAITING};
                border-radius: 9px;
                font-size: 7pt;
                font-weight: bold;
                border: 1px solid {Colors.STATE_WAITING};
            """)
        else:
            self.lbl_badge.setText("IDLE")
            self.lbl_badge.setStyleSheet(f"""
                background-color: {Colors.BG_BASE};
                color: {Colors.TEXT_MUTED};
                border-radius: 9px;
                font-size: 7pt;
                font-weight: bold;
                border: 1px solid {Colors.BORDER};
            """)

    def update_status(self, dev: Dict[str, Any]):
        # Support both boolean 'is_busy' and string 'status' key
        if "is_busy" in dev:
            is_busy = bool(dev["is_busy"])
        else:
            is_busy = str(dev.get("status", "IDLE")).upper() == "BUSY"

        self._set_badge(is_busy)
        self.lbl_queue.setText(f"Q: {dev.get('queue_length', 0)}")

        # Progress: support both 'progress' and 'progress_percent' keys
        progress = dev.get("progress_percent") or dev.get("progress") or 0

        if is_busy:
            pid  = dev.get("current_pid", "?")
            name = dev.get("current_name", "")
            self.lbl_current.setText(f"P{pid} ({name})" if name else f"PID {pid}")
            self.progress.setValue(int(progress))
        else:
            self.lbl_current.setText("—")
            self.progress.setValue(0)
