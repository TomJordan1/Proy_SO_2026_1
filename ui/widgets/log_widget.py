"""
ui/widgets/log_widget.py — Widget de Log del Sistema.
"""
from __future__ import annotations
from typing import List

from PySide6.QtWidgets import QTextEdit
from PySide6.QtGui import QTextCursor, QColor, QTextCharFormat
from PySide6.QtCore import Qt

from ui.styles import Colors

class LogWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }}
        """)
        self.document().setMaximumBlockCount(500)

    def append_messages(self, messages: List[str]):
        if not messages:
            return
            
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

        for msg in messages:
            fmt = QTextCharFormat()
            
            # Simple color coding based on content
            if "READY" in msg or "NEW" in msg:
                fmt.setForeground(QColor(Colors.LOG_READY))
            elif "RUNNING" in msg or "CTX" in msg or "PREEMPT" in msg:
                fmt.setForeground(QColor(Colors.LOG_RUNNING))
            elif "WAITING" in msg or "IO_REQ" in msg or "SYSCALL" in msg:
                fmt.setForeground(QColor(Colors.LOG_WAITING))
            elif "TERM" in msg or "ERROR" in msg:
                fmt.setForeground(QColor(Colors.LOG_ERROR))
            else:
                fmt.setForeground(QColor(Colors.LOG_INFO))

            cursor.insertText(msg + "\n", fmt)

        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def clear_log(self):
        self.clear()
