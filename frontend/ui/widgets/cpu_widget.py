"""
ui/widgets/cpu_widget.py — PatatOS CPU Cores visualizer.

Displays 1-4 CPU cores, each inside a QGroupBox showing:
  • Core ID and accent-colored header
  • State badge: IDLE / RUNNING / SWITCHING
  • Current process name + PID
  • Completion progress bar
  • Round-Robin quantum bar (shown only when quantum info is present)
  • Registers dictionary
  • Program Counter (PC) value
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.styles import Colors


# ── Helpers ────────────────────────────────────────────────────────────────────

def _badge(text: str, bg: str, fg: str = "#ffffff") -> QLabel:
    """Return a styled pill-shaped label used for state/type badges."""
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFixedHeight(20)
    lbl.setStyleSheet(
        f"background-color:{bg}; color:{fg}; border-radius:4px;"
        " font-size:8pt; font-weight:700; padding:0 6px;"
    )
    return lbl


def _progress_bar(color: str, height: int = 10) -> QProgressBar:
    """Return a minimal styled QProgressBar."""
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.setTextVisible(False)
    bar.setFixedHeight(height)
    bar.setStyleSheet(
        f"""
        QProgressBar {{
            background-color: {Colors.BG_ELEVATED};
            border: none;
            border-radius: {height // 2}px;
        }}
        QProgressBar::chunk {{
            background-color: {color};
            border-radius: {height // 2}px;
        }}
        """
    )
    return bar


# ── Per-core panel ─────────────────────────────────────────────────────────────

class _CorePanel(QGroupBox):
    """A single-core display panel inside a QGroupBox."""

    STATE_COLORS = {
        "RUNNING":   Colors.STATE_RUNNING,
        "IDLE":      Colors.STATE_TERMINATED,
        "SWITCHING": Colors.STATE_WAITING,
    }

    def __init__(self, core_id: int, accent: str, parent=None):
        super().__init__(f"Core {core_id}", parent)
        self._accent = accent
        self._core_id = core_id

        # Estilizar el borde del group box con el color de acento
        self.setStyleSheet(
            f"""
            QGroupBox {{
                border: 1px solid {accent};
                border-radius: 6px;
                margin-top: 14px;
                padding: 8px 6px 6px 6px;
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_PRIMARY};
                font-weight: 600;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px; top: 0px;
                padding: 0 4px;
                color: {accent};
                font-size: 9pt;
            }}
            QLabel {{ background: transparent; color: {Colors.TEXT_PRIMARY}; }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── State badge row ────────────────────────────────────────────────────
        row1 = QHBoxLayout()
        self._state_badge = _badge("IDLE", Colors.STATE_TERMINATED)
        self._state_badge.setFixedWidth(90)
        self._proc_label = QLabel("— idle —")
        self._proc_label.setStyleSheet(
            f"color:{Colors.TEXT_SEC}; font-size:9pt;"
        )
        row1.addWidget(self._state_badge)
        row1.addSpacing(6)
        row1.addWidget(self._proc_label)
        row1.addStretch()
        layout.addLayout(row1)

        # ── Completion progress bar ────────────────────────────────────────────
        lbl_comp = QLabel("Completion")
        lbl_comp.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:8pt;")
        layout.addWidget(lbl_comp)
        self._comp_bar = _progress_bar(accent)
        layout.addWidget(self._comp_bar)

        # ── Quantum bar (RR) ──────────────────────────────────────────────────
        self._quantum_row = QWidget()
        q_layout = QVBoxLayout(self._quantum_row)
        q_layout.setContentsMargins(0, 0, 0, 0)
        q_layout.setSpacing(2)
        lbl_q = QLabel("Quantum")
        lbl_q.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:8pt;")
        q_layout.addWidget(lbl_q)
        self._quantum_bar = _progress_bar(Colors.STATE_WAITING, height=8)
        q_layout.addWidget(self._quantum_bar)
        self._quantum_row.setVisible(False)
        layout.addWidget(self._quantum_row)

        # ── PC value ──────────────────────────────────────────────────────────
        pc_row = QHBoxLayout()
        pc_lbl = QLabel("PC:")
        pc_lbl.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:8pt;")
        self._pc_value = QLabel("0x0000")
        self._pc_value.setStyleSheet(
            f"color:{accent}; font-family:monospace; font-size:8pt;"
        )
        pc_row.addWidget(pc_lbl)
        pc_row.addWidget(self._pc_value)
        pc_row.addStretch()
        layout.addLayout(pc_row)

        # ── Registers ─────────────────────────────────────────────────────────
        self._reg_label = QLabel("Regs: —")
        self._reg_label.setStyleSheet(
            f"color:{Colors.TEXT_MUTED}; font-size:8pt; font-family:monospace;"
        )
        self._reg_label.setWordWrap(True)
        layout.addWidget(self._reg_label)

        layout.addStretch()

    # ── Public API ─────────────────────────────────────────────────────────────

    def refresh(self, snapshot: dict) -> None:
        """
        Update panel from a core snapshot dict.
        """
        is_busy = snapshot.get("is_busy", False)
        is_switching = snapshot.get("is_switching", False)

        if is_switching:
            state = "SWITCHING"
        elif is_busy:
            state = "RUNNING"
        else:
            state = "IDLE"

        color = self.STATE_COLORS.get(state, Colors.STATE_TERMINATED)
        self._state_badge.setText(state)
        self._state_badge.setStyleSheet(
            f"background-color:{color}; color:#fff; border-radius:4px;"
            " font-size:8pt; font-weight:700; padding:0 6px;"
        )

        proc = snapshot.get("process") or {}
        name = proc.get("name")
        pid  = proc.get("pid")
        
        if name and state != "IDLE":
            self._proc_label.setText(f"{name}  [PID {pid}]")
            self._proc_label.setStyleSheet(
                f"color:{Colors.TEXT_PRIMARY}; font-size:9pt; font-weight:600;"
            )
        else:
            self._proc_label.setText("— idle —")
            self._proc_label.setStyleSheet(
                f"color:{Colors.TEXT_SEC}; font-size:9pt;"
            )

        # Barra de progreso de completado
        comp = float(proc.get("completion") or 0)
        self._comp_bar.setValue(int(comp))

        # Barra de quantum (solo visible en RR/MLFQ)
        scheduler = str(snapshot.get("scheduler", "")).upper()
        is_rr = "RR" in scheduler or "ROUND" in scheduler or "MLFQ" in scheduler
        
        q_used  = proc.get("quantum_used")
        q_rem = proc.get("quantum_rem") or proc.get("quantum_remaining")
        if is_rr and q_used is not None and q_rem is not None:
            q_total = q_used + q_rem
            if q_total > 0:
                self._quantum_row.setVisible(True)
                pct = int(q_used / q_total * 100)
                self._quantum_bar.setValue(pct)
            else:
                self._quantum_row.setVisible(False)
        else:
            self._quantum_row.setVisible(False)

        # Contador de Programa (PC)
        pc = proc.get("pc", 0)
        if isinstance(pc, int):
            self._pc_value.setText(f"0x{pc:04X}")
        else:
            self._pc_value.setText(str(pc))

        # Registros
        regs = proc.get("registers")
        if regs and isinstance(regs, dict):
            parts = [f"{k}={v}" for k, v in list(regs.items())[:8]]
            self._reg_label.setText("Regs: " + "  ".join(parts))
        else:
            self._reg_label.setText("Regs: —")


# ── Main widget ────────────────────────────────────────────────────────────────

class CPUWidget(QWidget):
    """
    Horizontal row of 1-4 core panels.

    Usage::

        widget = CPUWidget(num_cores=4)
        widget.update(cores_snapshot)

    ``cores_snapshot`` is a list of dicts, one per core (see _CorePanel.refresh).
    """

    def __init__(self, num_cores: int = 1, parent=None):
        super().__init__(parent)
        self._num_cores = max(1, min(num_cores, 4))

        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        self._panels: list[_CorePanel] = []
        for i in range(self._num_cores):
            accent = Colors.CORE_COLORS[i % len(Colors.CORE_COLORS)]
            panel = _CorePanel(i, accent)
            panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            layout.addWidget(panel)
            self._panels.append(panel)

    # ── Public API ─────────────────────────────────────────────────────────────

    def update(self, cores_snapshot: list) -> None:  # type: ignore[override]
        """
        Refresh all core panels.

        :param cores_snapshot: list of dicts, one per core.  Missing entries
                               are treated as IDLE cores.
        """
        for i, panel in enumerate(self._panels):
            snap = cores_snapshot[i] if i < len(cores_snapshot) else {}
            panel.refresh(snap)
