"""
ui/widgets/pcb_table.py — PatatOS PCB Process Table.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer
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


_COLUMNS = [
    "PID", "Nombre", "Tipo", "Estado", "Prioridad",
    "Burst", "Restante", "Espera", "PC", "Mem (MB)", "Completado%", "···",
]
_COL_IDX = {name: i for i, name in enumerate(_COLUMNS)}

_ROW_DIM = {
    "TERMINATED": QColor(Colors.STATE_TERMINATED + "22"),
    "NEW":        QColor(Colors.STATE_NEW        + "11"),
}

# Estados previos obligatorios según la topología del diagrama de 5 estados.
# Se usa para "rellenar" transiciones que el motor de simulación atravesó
# tan rápido (dentro del mismo tick) que el polling de la UI nunca llegó
# a observarlas directamente — p.ej. un proceso que se admite y despacha
# a CPU en el mismo tick salta de NEW a RUNNING sin que la tabla vea READY.
_REQUIRED_PRECEDING = {
    "READY":      ["NEW"],
    "RUNNING":    ["NEW", "READY"],
    "WAITING":    ["NEW", "READY", "RUNNING"],
    "TERMINATED": ["NEW", "READY", "RUNNING"],
    "ERROR":      ["NEW", "READY", "RUNNING"],
}


def _item(text: str, align: Qt.AlignmentFlag = Qt.AlignCenter) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text))
    it.setTextAlignment(align | Qt.AlignVCenter)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


def _num_item(value: float | int, fmt: str = "{}") -> QTableWidgetItem:
    text = fmt.format(value) if value is not None else "—"
    it = QTableWidgetItem(text)
    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    it.setData(Qt.UserRole, float(value) if value is not None else -1.0)
    return it


class PCBTableWidget(QTableWidget):

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
        self._pid_row_map: dict[int, int] = {}
        self._state_history: dict[int, list[str]] = {}
        self._buttons: dict[int, QPushButton] = {}

        for col_name in ("PID", "Prioridad", "Burst", "Restante", "Espera",
                         "PC", "Completado%", "···"):
            idx = _COL_IDX.get(col_name)
            if idx is not None:
                self.horizontalHeader().setSectionResizeMode(
                    idx, QHeaderView.ResizeToContents)

        self.horizontalHeader().sortIndicatorChanged.connect(self._on_header_sort_changed)

        self.setStyleSheet(f"""
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
        """)

    @staticmethod
    def _get(proc, *keys, default=None):
        for key in keys:
            val = proc.get(key) if isinstance(proc, dict) else getattr(proc, key, None)
            if val is not None:
                return val
        return default

    def update(self, processes: list) -> None:  # type: ignore[override]
        self._procs = list(processes)
        g = self._get

        incoming: dict[int, Any] = {}
        for proc in processes:
            pid_raw = g(proc, "pid", default=None)
            try:
                pid = int(pid_raw)
            except (TypeError, ValueError):
                continue
            incoming[pid] = proc

        self.setUpdatesEnabled(False)
        self.setSortingEnabled(False)

        # Eliminar PIDs que ya no están
        removed = set(self._pid_row_map) - set(incoming)
        if removed:
            for row in sorted((self._pid_row_map[p] for p in removed), reverse=True):
                self.removeRow(row)
            for pid in removed:
                self._buttons.pop(pid, None)
            self._pid_row_map = {}
            for row in range(self.rowCount()):
                pid_item = self.item(row, _COL_IDX["PID"])
                if pid_item is not None:
                    self._pid_row_map[int(pid_item.data(Qt.UserRole))] = row

        # Insertar filas para PIDs nuevos
        for pid in incoming:
            if pid not in self._pid_row_map:
                row = self.rowCount()
                self.insertRow(row)
                self._pid_row_map[pid] = row
                self._build_row_items(row, pid)

        # Actualizar valores y acumular historial
        for pid, proc in incoming.items():
            row = self._pid_row_map[pid]
            self._refresh_row(row, proc)

            state = str(g(proc, "state", default="") or "").upper()
            if state:
                self._record_state_history(pid, state)

            if pid in self._open_dialogs:
                self._open_dialogs[pid].update_data(
                    proc if isinstance(proc, dict) else proc.__dict__)

        self.clearSelection()
        self.setCurrentItem(None)

        self.setSortingEnabled(True)
        self._resync_after_sort()

        self.setUpdatesEnabled(True)

    def _record_state_history(self, pid: int, state: str) -> None:
        """
        Acumula el historial de estados de un PID, rellenando los estados
        intermedios "saltados" la primera vez que vemos a ese proceso,
        según la topología obligatoria del diagrama.
        """
        history = self._state_history.setdefault(pid, [])
        if history and history[-1] == state:
            return  # sin cambio real desde el último poll

        if not history:
            for required in _REQUIRED_PRECEDING.get(state, []):
                if not history or history[-1] != required:
                    history.append(required)

        history.append(state)

    def _on_header_sort_changed(self, *_args) -> None:
        QTimer.singleShot(0, self._resync_after_sort)

    def _resync_after_sort(self) -> None:
        new_map: dict[int, int] = {}
        for row in range(self.rowCount()):
            pid_item = self.item(row, _COL_IDX["PID"])
            if pid_item is None:
                continue
            pid = int(pid_item.data(Qt.UserRole))
            new_map[pid] = row
            btn = self._buttons.get(pid)
            if btn is not None:
                self.setCellWidget(row, _COL_IDX["···"], btn)
        self._pid_row_map = new_map

    def _build_row_items(self, row: int, pid: int) -> None:
        for col in range(len(_COLUMNS) - 1):
            if col == _COL_IDX["Nombre"]:
                item = _item("", Qt.AlignLeft)
            elif col == _COL_IDX["PID"]:
                item = _num_item(pid, fmt="{:.0f}")
            elif col in (_COL_IDX["Prioridad"], _COL_IDX["Burst"],
                         _COL_IDX["Restante"], _COL_IDX["Espera"],
                         _COL_IDX["Mem (MB)"], _COL_IDX["Completado%"]):
                item = _num_item(0)
            else:
                item = _item("")
            self.setItem(row, col, item)

        btn = QPushButton("···")
        btn.setFixedSize(30, 20)
        btn.setStyleSheet(
            f"QPushButton {{ background:{Colors.BG_ELEVATED}; color:{Colors.ACCENT_LIGHT};"
            f" border:1px solid {Colors.BORDER}; border-radius:3px; font-size:9pt; }}"
            f"QPushButton:hover {{ background:{Colors.ACCENT_DARK}; }}"
        )
        btn.clicked.connect(lambda _, p=pid: self._open_inspector_by_pid(p))
        self._buttons[pid] = btn
        self.setCellWidget(row, _COL_IDX["···"], btn)

    def _refresh_row(self, row: int, proc: Any) -> None:
        g = self._get
        state     = (g(proc, "state", default="") or "").upper()
        proc_type = g(proc, "type_label", "process_type", "type", default="") or ""
        if hasattr(proc_type, "value"):
            proc_type = proc_type.value
        proc_type = str(proc_type).upper()
        name      = g(proc, "name", "process_name", default="?")
        priority  = g(proc, "priority",        default=None)
        burst     = g(proc, "burst_time",      default=None)
        remaining = g(proc, "remaining_time",  default=None)
        waiting   = g(proc, "waiting_time",    default=None)
        pc_val    = g(proc, "program_counter", "pc", default=0)
        mem       = g(proc, "memory_size", "memory_mb", "memory", default=None)
        comp      = g(proc, "completion_percent", "completion_pct", default=None)

        def set_text(col, text, align=Qt.AlignCenter):
            item = self.item(row, col)
            if item: item.setText(str(text)); item.setTextAlignment(align|Qt.AlignVCenter)

        def set_num(col, value, fmt="{}"):
            item = self.item(row, col)
            if item:
                item.setText(fmt.format(value) if value is not None else "—")
                item.setData(Qt.UserRole, float(value) if value is not None else -1.0)

        set_num(_COL_IDX["PID"],        g(proc, "pid", default=0), fmt="{:.0f}")
        set_text(_COL_IDX["Nombre"],    name, Qt.AlignLeft)
        set_text(_COL_IDX["Tipo"],      proc_type)
        set_text(_COL_IDX["Estado"],    state)
        set_num(_COL_IDX["Prioridad"],  priority or 0)
        set_num(_COL_IDX["Burst"],      burst or 0)
        set_num(_COL_IDX["Restante"],   remaining or 0)
        set_num(_COL_IDX["Espera"],     waiting or 0)
        set_text(_COL_IDX["PC"],
                 f"0x{pc_val:04X}" if isinstance(pc_val, int) else str(pc_val))
        set_num(_COL_IDX["Mem (MB)"],   mem or 0,  fmt="{:.1f}")
        set_num(_COL_IDX["Completado%"], comp or 0, fmt="{:.1f}%")

        row_bg   = _ROW_DIM.get(state)
        base_bg  = QBrush(row_bg) if row_bg else QBrush()

        for col in range(len(_COLUMNS) - 1):
            item = self.item(row, col)
            if item:
                item.setBackground(base_bg)
                item.setForeground(QBrush(QColor(Colors.TEXT_PRIMARY)))

        tipo_item = self.item(row, _COL_IDX["Tipo"])
        tc = TYPE_COLORS.get(proc_type)
        if tc and tipo_item:
            tipo_item.setForeground(QBrush(QColor(tc)))

        estado_item = self.item(row, _COL_IDX["Estado"])
        sc = STATE_COLORS.get(state)
        if sc and estado_item:
            estado_item.setBackground(QBrush(QColor(sc + "55")))
            estado_item.setForeground(QBrush(QColor(sc)))

    def _open_inspector_by_pid(self, pid: int) -> None:
        proc = None
        for p in self._procs:
            try:
                if int(self._get(p, "pid", default=-1)) == pid:
                    proc = p; break
            except (TypeError, ValueError):
                continue
        if proc is None:
            return
        proc_dict = dict(proc) if isinstance(proc, dict) else proc.__dict__
        self._open_inspector(proc_dict, pid)

    def _open_inspector(self, proc: dict, pid: int) -> None:
        if pid in self._open_dialogs:
            dlg = self._open_dialogs[pid]
            dlg.raise_(); dlg.activateWindow()
            return

        dlg = PCBDetailDialog(proc, self)

        history = self._state_history.get(pid, [])
        if history:
            dlg.load_history(history)

        self._open_dialogs[pid] = dlg
        dlg.finished.connect(lambda: self._open_dialogs.pop(pid, None))
        dlg.show()