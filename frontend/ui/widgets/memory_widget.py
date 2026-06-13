"""
ui/widgets/memory_widget.py — PatatOS linear memory visualizer.

Paints a proportional horizontal bar where each segment is colored by type:
  • OS segment      → Colors.MEM_OS
  • Free segment    → Colors.MEM_FREE
  • .text segment   → Colors.MEM_TEXT
  • .data segment   → Colors.MEM_DATA
  • heap segment    → Colors.MEM_HEAP
  • stack segment   → Colors.MEM_STACK
  • generic/other   → pid_color(pid)

Hover shows segment label + MB size in a tooltip-style overlay.

Below the bar: fragmentation %, used/free MB, strategy name.
Optional MMU panel: logical → physical address table.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.styles import Colors, pid_color


# ── Segment-type → colour mapping ─────────────────────────────────────────────

_SEG_COLORS: dict[str, str] = {
    "os":    Colors.MEM_OS,
    "free":  Colors.MEM_FREE,
    "text":  Colors.MEM_TEXT,
    "data":  Colors.MEM_DATA,
    "heap":  Colors.MEM_HEAP,
    "stack": Colors.MEM_STACK,
}


def _seg_color(seg: Any) -> QColor:
    if isinstance(seg, dict):
        seg_type = str(seg.get("segment_type") or seg.get("type") or "").lower()
        pid = seg.get("process_id") or seg.get("pid")
        is_free = seg.get("is_free", pid is None)
    else:
        st = getattr(seg, "segment_type", "")
        seg_type = str(st).split('.')[-1].lower() if st else ""
        pid = getattr(seg, "process_id", None)
        is_free = getattr(seg, "is_free", True)

    if seg_type == "os":
        return QColor(Colors.MEM_OS)
    if is_free or seg_type == "free" or pid is None:
        return QColor(Colors.MEM_FREE)

    # Process segments — use type-specific colors
    color_map = {
        "text":  Colors.MEM_TEXT,
        "data":  Colors.MEM_DATA,
        "heap":  Colors.MEM_HEAP,
        "stack": Colors.MEM_STACK,
    }
    if seg_type in color_map:
        return QColor(color_map[seg_type])

    # Unknown process segment — fall back to pid color
    return QColor(pid_color(int(pid)))


def _seg_size(seg: Any) -> float:
    if isinstance(seg, dict):
        return float(seg.get("size") or seg.get("size_kb") or 0)
    return float(getattr(seg, "size", 0))

def _seg_label(seg: Any) -> str:
    if isinstance(seg, dict):
        lbl = seg.get("label") or seg.get("name")
        if lbl: return str(lbl)
        stype = str(seg.get("segment_type") or seg.get("type") or "?").split('.')[-1]
        pid = seg.get("process_id") or seg.get("pid")
        if pid is not None:
            return f"P{pid} [{stype}]"
        return stype

    pid = getattr(seg, "process_id", None)
    st = getattr(seg, "segment_type", "")
    stype = str(st).split('.')[-1] if st else "?"
    if pid is not None:
        return f"P{pid} [{stype}]"
    return stype


# ── Memory bar canvas ─────────────────────────────────────────────────────────

class _MemoryBar(QWidget):
    """QPainter canvas that draws the proportional memory bar."""

    BAR_H     = 40     # bar height in px
    LABEL_H   = 16     # label row height below bar
    TOTAL_H   = BAR_H + LABEL_H + 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments: list[dict] = []
        self._total_kb: float = 1.0
        self._hover_seg: dict | None = None
        self._hover_pos: QPoint = QPoint()
        self.setMinimumHeight(self.TOTAL_H)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(self.TOTAL_H)

    def set_segments(self, segments: list, total_mb: int) -> None:
        self._segments = segments
        self._total_mb = max(total_mb, 1)
        self.update()

    # ── Mouse hover ───────────────────────────────────────────────────────────

    def mouseMoveEvent(self, event):
        x = event.position().x()
        w = self.width()
        seg = self._seg_at_x(x, w)
        if seg != self._hover_seg:
            self._hover_seg  = seg
            self._hover_pos  = event.position().toPoint()
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_seg = None
        self.update()
        super().leaveEvent(event)

    def _seg_at_x(self, x: float, total_w: int) -> Any | None:
        offset = 0.0
        for seg in self._segments:
            size = _seg_size(seg)
            frac = size / self._total_mb
            seg_w = frac * total_w
            if offset <= x < offset + seg_w:
                return seg
            offset += seg_w
        return None

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.BAR_H
        r = 6  # corner radius

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(Colors.BG_ELEVATED))
        painter.drawRoundedRect(0, 0, w, h, r, r)

        # Segments
        offset = 0
        for seg in self._segments:
            size = _seg_size(seg)
            frac = size / self._total_mb
            seg_w = max(int(frac * w), 1)
            color = _seg_color(seg)
            # Highlight hovered segment
            if seg is self._hover_seg:
                color = color.lighter(140)
            painter.setBrush(color)
            painter.drawRect(offset, 0, seg_w, h)
            offset += seg_w

        # Border overlay
        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(0, 0, w - 1, h - 1, r, r)

        # Hover tooltip bubble
        if self._hover_seg:
            seg = self._hover_seg
            label  = _seg_label(seg)
            size   = _seg_size(seg)
            mb_str = f"{size:.1f} MB"
            text   = f"{label}  {mb_str}"
            fm     = painter.fontMetrics()
            tw     = fm.horizontalAdvance(text) + 16
            th     = fm.height() + 8
            tx     = min(self._hover_pos.x(), w - tw - 4)
            ty     = h + 4
            painter.setBrush(QColor(Colors.BG_CARD))
            painter.setPen(QPen(QColor(Colors.BORDER), 1))
            painter.drawRoundedRect(tx, ty, tw, th, 4, 4)
            painter.setPen(QColor(Colors.TEXT_PRIMARY))
            painter.drawText(tx + 8, ty + th - (th - fm.height()) // 2 - 2, text)

        painter.end()


# ── Stats row ─────────────────────────────────────────────────────────────────

def _stat_label(title: str, value: str = "—", color: str = Colors.TEXT_PRIMARY) -> QWidget:
    """A mini card showing a stat value + label below."""
    w = QWidget()
    w.setStyleSheet(
        f"background:{Colors.BG_CARD}; border:1px solid {Colors.BORDER};"
        " border-radius:5px; padding:4px 8px;"
    )
    ly = QVBoxLayout(w)
    ly.setSpacing(0)
    ly.setContentsMargins(6, 4, 6, 4)
    val_lbl = QLabel(value)
    val_lbl.setObjectName("val")
    val_lbl.setStyleSheet(
        f"color:{color}; font-size:10pt; font-weight:700; background:transparent; border:none;"
    )
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(
        f"color:{Colors.TEXT_MUTED}; font-size:7pt; background:transparent; border:none;"
    )
    ly.addWidget(val_lbl)
    ly.addWidget(title_lbl)
    w._val_lbl = val_lbl  # type: ignore[attr-defined]
    return w


# ── MMU mini table ────────────────────────────────────────────────────────────

class _MMUPanel(QWidget):
    """Two-column table: Logical Address → Physical Address."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)

        hdr = QLabel("MMU — Page Table")
        hdr.setStyleSheet(
            f"color:{Colors.ACCENT_LIGHT}; font-size:9pt; font-weight:600;"
        )
        layout.addWidget(hdr)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Logical", "Physical"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setMaximumHeight(130)
        self._table.setStyleSheet(
            f"""
            QTableWidget {{
                background:{Colors.BG_SURFACE}; border:1px solid {Colors.BORDER};
                font-family:monospace; font-size:8pt; color:{Colors.TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background:{Colors.BG_ELEVATED}; color:{Colors.TEXT_SEC};
                border:none; border-bottom:1px solid {Colors.BORDER}; padding:2px 4px;
            }}
            """
        )
        layout.addWidget(self._table)

    def refresh(self, mmu_table: dict) -> None:
        self._table.setRowCount(0)
        if not mmu_table:
            return
        # mmu_table is {pid: {"logical_base": ..., "physical_base": ..., "size": ...}}
        for pid, info in mmu_table.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            li = QTableWidgetItem(f"0x{info.get('logical_base', 0):04X} (P{pid})")
            pi = QTableWidgetItem(f"0x{info.get('physical_base', 0):04X}")
            li.setFlags(li.flags() & ~Qt.ItemFlag.ItemIsEditable)
            pi.setFlags(pi.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 0, li)
            self._table.setItem(row, 1, pi)


# ── Main widget ───────────────────────────────────────────────────────────────

class MemoryWidget(QWidget):
    """
    Linear memory visualizer with hover labels, stats, and optional MMU panel.

    Usage::

        widget = MemoryWidget()
        widget.update(segments, stats)

    ``segments`` – list of dicts with keys:
        label/name  str
        type        str  ("os" | "free" | "text" | "data" | "heap" | "stack")
        size_kb     int  (or "size" for generic KB value)
        pid         int  (optional, used if type is unrecognised)

    ``stats`` – dict with optional keys:
        total_kb        float
        used_kb         float
        free_kb         float
        fragmentation   float  (0-100 %)
        strategy        str
        mmu_table       list[tuple[str,str]]  – (logical, physical)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(0, 0, 0, 0)

        # Header label
        hdr = QLabel("Memory Map")
        hdr.setStyleSheet(
            f"color:{Colors.ACCENT_LIGHT}; font-size:10pt; font-weight:700;"
        )
        root.addWidget(hdr)

        # Bar
        self._bar = _MemoryBar()
        root.addWidget(self._bar)

        # Stats row ────────────────────────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(6)

        self._s_frag  = _stat_label("Fragmentation", "—", Colors.STATE_WAITING)
        self._s_used  = _stat_label("Used",          "—", Colors.STATE_RUNNING)
        self._s_free  = _stat_label("Free",          "—", Colors.STATE_READY)
        self._s_strat = _stat_label("Strategy",      "—", Colors.TEXT_SEC)

        for w in (self._s_frag, self._s_used, self._s_free, self._s_strat):
            stats_row.addWidget(w)
        stats_row.addStretch()
        root.addLayout(stats_row)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color:{Colors.BORDER};")
        root.addWidget(line)

        # MMU panel
        self._mmu = _MMUPanel()
        self._mmu.setVisible(False)
        root.addWidget(self._mmu)

        root.addStretch()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _set_val(card: QWidget, value: str) -> None:
        card._val_lbl.setText(value)  # type: ignore[attr-defined]

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, segments: list, stats: dict, mmu_table: dict = None) -> None:  # type: ignore[override]
        """
        Refresh the memory visualizer.

        :param segments: list of segment dicts.
        :param stats:    stats dict (see class docstring).
        """
        total_mb = float(stats.get("total_mb") or 1)
        self._bar.set_segments(segments, total_mb)

        # Stats cards
        frag  = stats.get("fragmentation")
        used  = stats.get("used_mb")
        free  = stats.get("free_mb")
        strat = stats.get("strategy") or "—"

        self._set_val(self._s_frag,  f"{frag:.1f}%" if frag is not None else "—")
        self._set_val(self._s_used,  f"{used:.1f} MB" if used is not None else "—")
        self._set_val(self._s_free,  f"{free:.1f} MB" if free is not None else "—")
        self._set_val(self._s_strat, strat)

        # MMU table
        mmu = mmu_table if mmu_table is not None else stats.get("mmu_table")
        if mmu:
            self._mmu.setVisible(True)
            self._mmu.refresh(mmu)
        else:
            self._mmu.setVisible(False)
