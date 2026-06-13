"""
ui/widgets/pcb_table.py — PatatOS PCB Process Table.

A QTableWidget displaying all processes with columns:
    PID | Nombre | Tipo | Estado | Prioridad | Burst | Restante | Espera |
    PC | Mem(MB) | Completado%

Rows are coloured by process state using STATE_COLORS.
The State cell background is highlighted with the state colour.
The table is sortable by clicking column headers.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from ui.styles import Colors, STATE_COLORS, TYPE_COLORS
from ui.widgets.pcb_detail_dialog import PCBDetailDialog


# ── Column definitions ────────────────────────────────────────────────────────

_COLUMNS = [
    "PID",
    "Nombre",
    "Tipo",
    "Estado",
    "Prioridad",
    "Burst",
    "Restante",
    "Espera",
    "PC",
    "Mem (MB)",
    "Completado%",
    "···",
]

_COL_IDX = {name: i for i, name in enumerate(_COLUMNS)}

# Dim row tint for non-active states (alpha overlay)
_ROW_DIM = {
    "TERMINATED": QColor(Colors.STATE_TERMINATED + "22"),
    "NEW":        QColor(Colors.STATE_NEW        + "11"),
}


# ── Item helpers ──────────────────────────────────────────────────────────────

def _item(text: str, align: Qt.AlignmentFlag = Qt.AlignCenter) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text))
    it.setTextAlignment(align | Qt.AlignVCenter)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


def _num_item(value: float | int, fmt: str = "{}") -> QTableWidgetItem:
    """Numeric item that sorts correctly by storing value as UserRole."""
    text = fmt.format(value) if value is not None else "—"
    it = QTableWidgetItem(text)
    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    it.setData(Qt.UserRole, float(value) if value is not None else -1.0)
    return it


# ── Widget ────────────────────────────────────────────────────────────────────

class PCBTableWidget(QTableWidget):
    """
    Sortable process table widget.

    Usage::

        table = PCBTableWidget()
        table.update(processes)

    ``processes`` is a list of PCB-like objects or dicts with attributes/keys:
        pid, name/process_name, type, state, priority, burst_time,
        remaining_time, waiting_time, pc, memory_mb/memory, completion_pct
    """

    def __init__(self, parent=None):
        super().__init__(0, len(_COLUMNS), parent)

        self.setHorizontalHeaderLabels(_COLUMNS)
        self.setSortingEnabled(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.horizontalHeader().setMinimumSectionSize(45)
        self._procs: list = []
        self._open_dialogs: dict[int, PCBDetailDialog] = {}

        # Fix column widths for narrow columns
        for col_name in ("PID", "Prioridad", "Burst", "Restante", "Espera",
                         "PC", "Completado%", "···"):
            idx = _COL_IDX.get(col_name)
            if idx is not None:
                self.horizontalHeader().setSectionResizeMode(
                    idx, QHeaderView.ResizeToContents
                )

        # Store proc data for inspector dialog
        self._procs: list = []

        self.setStyleSheet(
            f"""
            QTableWidget {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                gridline-color: {Colors.BORDER};
                selection-background-color: {Colors.ACCENT_DARK};
                color: {Colors.TEXT_PRIMARY};
            }}
            QTableWidget::item {{ padding: 3px 6px; }}
            QHeaderView::section {{
                background-color: {Colors.BG_ELEVATED};
                border: none;
                border-bottom: 1px solid {Colors.BORDER};
                border-right: 1px solid {Colors.BORDER};
                padding: 4px 6px;
                color: {Colors.TEXT_SEC};
                font-weight: 600;
                font-size: 8pt;
            }}
            QTableWidget::item:selected {{
                background-color: {Colors.ACCENT_DARK};
                color: #fff;
            }}
            """
        )

    # ── Attribute accessor (supports both dict and object) ────────────────────

    @staticmethod
    def _get(proc, *keys, default=None):
        for key in keys:
            if isinstance(proc, dict):
                val = proc.get(key)
            else:
                val = getattr(proc, key, None)
            if val is not None:
                return val
        return default

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, processes: list) -> None:  # type: ignore[override]
        """Repopulate the table from a list of PCB objects or dicts."""
        self._procs = list(processes)   # store for inspector
        # Disable sorting during repopulation to avoid mid-insert reorders
        self.setSortingEnabled(False)
        self.setRowCount(0)

        g = self._get  # shorthand

        for proc in processes:
            pid       = g(proc, "pid",    default="—")
            
            # Update open inspector if it exists
            if pid in self._open_dialogs:
                self._open_dialogs[pid].update_data(proc if isinstance(proc, dict) else proc.__dict__)
                
            row = self.rowCount()
            self.insertRow(row)

            state     = (g(proc, "state", default="") or "").upper()
            proc_type = (g(proc, "type_label", "process_type", "type", default="") or "")
            if hasattr(proc_type, "value"):
                proc_type = proc_type.value
            proc_type = str(proc_type).upper()
            pid       = g(proc, "pid",    default="—")
            name      = g(proc, "name", "process_name", default="?")
            priority  = g(proc, "priority",        default=None)
            burst     = g(proc, "burst_time",      default=None)
            remaining = g(proc, "remaining_time",  default=None)
            waiting   = g(proc, "waiting_time",    default=None)
            pc_val    = g(proc, "program_counter", "pc", default=0)
            mem       = g(proc, "memory_size", "memory_mb", "memory", default=None)
            comp      = g(proc, "completion_percent", "completion_pct", default=None)

            # ── Row colour ───────────────────────────────────────────────────
            row_bg = _ROW_DIM.get(state)

            # ── Cells ────────────────────────────────────────────────────────
            cells = [
                _num_item(pid if isinstance(pid, (int, float)) else 0,
                          fmt="{:.0f}"),                                # PID
                _item(name, Qt.AlignLeft),                              # Nombre
                _item(proc_type),                                       # Tipo
                _item(state),                                           # Estado
                _num_item(priority or 0),                               # Prioridad
                _num_item(burst    or 0),                               # Burst
                _num_item(remaining or 0),                              # Restante
                _num_item(waiting   or 0),                              # Espera
                _item(f"0x{pc_val:04X}" if isinstance(pc_val, int)
                      else str(pc_val)),                                # PC
                _num_item(mem  or 0, fmt="{:.1f}"),                     # Mem
                _num_item(comp or 0, fmt="{:.1f}%"),                    # Comp%
            ]

            for col, cell in enumerate(cells):
                # Row background tint
                if row_bg:
                    cell.setBackground(QBrush(row_bg))

                # Type column colour
                if col == _COL_IDX["Tipo"]:
                    tc = TYPE_COLORS.get(proc_type)
                    if tc:
                        cell.setForeground(QBrush(QColor(tc)))

                # State column: coloured background
                if col == _COL_IDX["Estado"]:
                    sc = STATE_COLORS.get(state)
                    if sc:
                        cell.setBackground(QBrush(QColor(sc + "55")))
                        cell.setForeground(QBrush(QColor(sc)))

                self.setItem(row, col, cell)

            # ── Inspector button ─────────────────────────────────────────────
            btn = QPushButton("···")
            btn.setFixedSize(30, 20)
            btn.setStyleSheet(
                f"QPushButton {{ background:{Colors.BG_ELEVATED}; color:{Colors.ACCENT_LIGHT};"
                f" border:1px solid {Colors.BORDER}; border-radius:3px; font-size:9pt; }}"
                f"QPushButton:hover {{ background:{Colors.ACCENT_DARK}; }}"
            )
            # Capture proc dict for the lambda closure
            proc_dict = dict(proc) if isinstance(proc, dict) else proc.__dict__
            btn.clicked.connect(lambda _, p=proc_dict: self._open_inspector(p))
            self.setCellWidget(row, _COL_IDX["···"], btn)

        self.setSortingEnabled(True)

    def _open_inspector(self, proc: dict):
        pid = proc.get("pid")
        if pid in self._open_dialogs:
            dlg = self._open_dialogs[pid]
            dlg.raise_()
            dlg.activateWindow()
            return
            
        dlg = PCBDetailDialog(proc, self)
        self._open_dialogs[pid] = dlg
        dlg.finished.connect(lambda: self._open_dialogs.pop(pid, None))
        dlg.show()

