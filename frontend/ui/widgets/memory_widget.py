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
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QDialog,
    QComboBox,
    QHeaderView,
    QGridLayout,
)

from ui.styles import Colors, pid_color


# ── Tipo de segmento → mapeo de colores ─────────────────────────────────────────────

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

    # Segmento de procesos — use type-specific colors
    color_map = {
        "text":  Colors.MEM_TEXT,
        "data":  Colors.MEM_DATA,
        "heap":  Colors.MEM_HEAP,
        "stack": Colors.MEM_STACK,
    }
    if seg_type in color_map:
        return QColor(color_map[seg_type])

    if seg_type == "swap_used":
        return QColor("#8b5cf6") # Púrpura para swap
    if seg_type == "swap_free":
        return QColor(Colors.MEM_FREE)

    # Segmento del proceso desconocido — recurrir al pid color
    return QColor(pid_color(int(pid) if pid is not None else 0))


def _seg_size(seg: Any) -> float:
    if isinstance(seg, dict):
        if "size_mb" in seg:
            return float(seg["size_mb"])
        return float(seg.get("size") or seg.get("size_kb") or 0) / 1024.0
    val = float(getattr(seg, "size", 0))
    return val / 1024.0 if val > 0 else 0.0

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


# ── Lienzo de la barra de memoria ─────────────────────────────────────────────────────────

class _MemoryBar(QWidget):
    """QPainter canvas that draws the proportional memory bar."""

    BAR_H     = 40     # altura de la barra en px
    LABEL_H   = 16     # altura de la fila de etiquetas debajo de la barra
    TOTAL_H   = BAR_H + LABEL_H + 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments: list[dict] = []
        self._total_mb: float = 1.0
        self._hover_seg: dict | None = None
        self._hover_pos: QPoint = QPoint()
        self._seg_rects: list[tuple[int, int, Any]] = []  # (x, ancho, seg) cacheados
        self.setMinimumHeight(self.TOTAL_H)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(self.TOTAL_H)

    def set_segments(self, segments: list, total_mb: int) -> None:
        self._segments = segments
        self._total_mb = max(total_mb, 1)
        self._recalculate_rects()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._recalculate_rects()

    def _recalculate_rects(self) -> None:
        w = self.width()
        rects = []
        cumulative = 0.0
        prev_x = 0

        for seg in self._segments:
            size_val = _seg_size(seg)
            cumulative += size_val
            frac = cumulative / self._total_mb if self._total_mb > 0 else 0
            x_end = round(frac * w)
            seg_w = max(x_end - prev_x, 0)
            
            # Enforce minimum width for visible process segments (so tiny pages don't disappear)
            if size_val > 0:
                seg_type = str(seg.get("segment_type") or seg.get("type") or "").lower()
                is_free = seg.get("is_free", seg.get("pid") is None)
                if not is_free and seg_type != "os" and seg_w < 2:
                    seg_w = 2
                    x_end = prev_x + 2

            rects.append((prev_x, seg_w, seg))
            prev_x = x_end

        self._seg_rects = rects

    # ── Desplazamiento del mouse ───────────────────────────────────────────────────────────

    def mouseMoveEvent(self, event):
        x = event.position().x()
        seg = self._seg_at_x(x)
        if seg != self._hover_seg:
            self._hover_seg  = seg
            self._hover_pos  = event.position().toPoint()
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_seg = None
        self.update()
        super().leaveEvent(event)

    def _seg_at_x(self, x: float) -> Any | None:
        for seg_x, seg_w, seg in self._seg_rects:
            if seg_x <= x < seg_x + seg_w:
                return seg
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

        # Segments — usa los mismos rects cacheados que _seg_at_x
        for seg_x, seg_w, seg in self._seg_rects:
            if seg_w <= 0:
                continue
            color = _seg_color(seg)
            if seg is self._hover_seg:
                color = color.lighter(140)
            painter.setBrush(color)
            painter.drawRect(seg_x, 0, seg_w, h)

        # Draw Addressing Grid (Rejilla de direccionamiento cada 16MB) solo si es paginada
        if self._is_paged and self._total_mb > 0:
            grid_color = QColor(Colors.TEXT_MUTED)
            grid_color.setAlpha(100)
            painter.setPen(QPen(grid_color, 1, Qt.PenStyle.DashLine))
            page_size = 16
            num_pages = int(self._total_mb // page_size)
            scale = w / self._total_mb
            for i in range(1, num_pages + 1):
                mb = i * page_size
                if mb >= self._total_mb:
                    continue
                x = int(mb * scale)
                painter.drawLine(x, 0, x, h)
                # Label
                painter.setPen(QColor(Colors.TEXT_MUTED))
                painter.drawText(x + 2, h - 2, f"{mb}")
                painter.setPen(QPen(grid_color, 1, Qt.PenStyle.DashLine))

        # Superposición de bordes
        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(0, 0, w - 1, h - 1, r, r)

        # Burbuja de información sobre herramientas al pasar el cursor
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


class _SwapPieChart(QWidget):
    """QPainter canvas that draws a pie chart for Swap usage."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.used_mb = 0.0
        self.free_mb = 0.0
        self.total_mb = 0.0
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(120)

    def set_values(self, used_mb: float, total_mb: float):
        self.used_mb = used_mb
        self.total_mb = total_mb
        self.free_mb = max(0.0, total_mb - used_mb)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Pie Chart limits
        size = min(w // 2, h) - 20
        rect_x = 20
        rect_y = (h - size) // 2
        
        if self.total_mb > 0:
            angle = int((self.used_mb / self.total_mb) * 360 * 16)
        else:
            angle = 0
            
        # Draw Used
        painter.setBrush(QColor(Colors.STATE_ERROR)) 
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPie(rect_x, rect_y, size, size, 90 * 16, -angle)
        
        # Draw Free
        painter.setBrush(QColor(Colors.BORDER)) 
        painter.drawPie(rect_x, rect_y, size, size, 90 * 16 - angle, -(360 * 16 - angle))
        
        # Draw border
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QColor(Colors.BG_BASE))
        painter.drawEllipse(rect_x, rect_y, size, size)
        
        # Legend
        text_x = rect_x + size + 40
        painter.setPen(QColor(Colors.TEXT_PRIMARY))
        
        painter.drawText(text_x, 35, f"Almacenamiento Swap: {self.total_mb:.1f} MB")
        
        painter.setBrush(QColor(Colors.STATE_ERROR))
        painter.drawRect(text_x, 55, 12, 12)
        painter.drawText(text_x + 20, 66, f"Usado: {self.used_mb:.1f} MB")
        
        painter.setBrush(QColor(Colors.BORDER))
        painter.drawRect(text_x, 80, 12, 12)
        painter.drawText(text_x + 20, 91, f"Libre: {self.free_mb:.1f} MB")
        
        painter.end()


# ── Fila de estadisticas ─────────────────────────────────────────────────────────────────

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

        # Header row
        hdr_layout = QHBoxLayout()
        hdr = QLabel("Memory Map")
        hdr.setStyleSheet(
            f"color:{Colors.ACCENT_LIGHT}; font-size:10pt; font-weight:700;"
        )
        hdr_layout.addWidget(hdr)
        
        self._btn_vm = QPushButton("🔍 Inspector VM")
        self._btn_vm.setStyleSheet(f"background:{Colors.BG_ELEVATED}; border:1px solid {Colors.BORDER}; color:{Colors.ACCENT_LIGHT}; padding:4px 8px; border-radius:4px;")
        self._btn_vm.setVisible(False)
        self._btn_vm.clicked.connect(self._show_vm_inspector)
        hdr_layout.addWidget(self._btn_vm)
        hdr_layout.addStretch()
        
        root.addLayout(hdr_layout)
        # Bar
        self._bar = _MemoryBar()
        root.addWidget(self._bar)

        # Swap
        self._swap_bar = _SwapPieChart()
        self._swap_bar.setVisible(False)
        root.addWidget(self._swap_bar)

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

    def _show_vm_inspector(self):
        from PySide6.QtWidgets import QDialog, QTabWidget, QTableWidgetItem
        from PySide6.QtGui import QIcon

        if not hasattr(self, "_vm_dialog") or self._vm_dialog is None:
            self._vm_dialog = QDialog(self)
            self._vm_dialog.setWindowTitle("Inspector de Memoria Virtual")
            self._vm_dialog.resize(600, 400)
            self._vm_dialog.setModal(False) # No intrusivo
            
            ly = QVBoxLayout(self._vm_dialog)
            
            self._vm_tabs = QTabWidget()
            
            # TLB Tab
            self._tlb_tab = QWidget()
            t_ly = QVBoxLayout(self._tlb_tab)
            self._tlb_lbl = QLabel()
            t_ly.addWidget(self._tlb_lbl)
            self._tlb_table = QTableWidget(0, 3)
            self._tlb_table.setHorizontalHeaderLabels(["PID", "VPN", "Frame"])
            t_ly.addWidget(self._tlb_table)
            self._vm_tabs.addTab(self._tlb_tab, "TLB")
            
            # Page Table Tab
            self._pt_tab = QWidget()
            p_ly = QVBoxLayout(self._pt_tab)
            
            # Layout horizontal para controles
            h_ly = QHBoxLayout()
            h_ly.addWidget(QLabel("Proceso:"))
            self._pt_combo = __import__('PySide6.QtWidgets', fromlist=['QComboBox']).QComboBox()
            self._pt_combo.currentIndexChanged.connect(self._on_pt_combo_change)
            h_ly.addWidget(self._pt_combo)
            h_ly.addStretch()
            p_ly.addLayout(h_ly)
            
            self._pt_table = QTableWidget(0, 5)
            self._pt_table.setHorizontalHeaderLabels(["VPN", "Frame", "Valid (V)", "Ref (R)", "Mod (M)"])
            p_ly.addWidget(self._pt_table)
            self._vm_tabs.addTab(self._pt_tab, "Page Tables")
            
            # Swap Tab
            self._swap_tab = QWidget()
            s_ly = QVBoxLayout(self._swap_tab)
            self._swap_lbl = QLabel()
            s_ly.addWidget(self._swap_lbl)
            self._vm_tabs.addTab(self._swap_tab, "Swap")
            
            ly.addWidget(self._vm_tabs)

        self._refresh_vm_dialog()
        if not self._vm_dialog.isVisible():
            self._vm_dialog.show()

    def _refresh_vm_dialog(self):
        if not hasattr(self, "_vm_dialog") or not self._vm_dialog.isVisible():
            return
            
        d = self._paged_data
        if not d: return
        
        tlb = d.get("tlb", {})
        self._tlb_lbl.setText(f"Hits: {tlb.get('hits', 0)} | Misses: {tlb.get('misses', 0)}")
        entries = tlb.get("entries", [])
        self._tlb_table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            self._tlb_table.setItem(i, 0, __import__('PySide6.QtWidgets', fromlist=['QTableWidgetItem']).QTableWidgetItem(str(e.get("pid"))))
            self._tlb_table.setItem(i, 1, __import__('PySide6.QtWidgets', fromlist=['QTableWidgetItem']).QTableWidgetItem(str(e.get("vpn"))))
            self._tlb_table.setItem(i, 2, __import__('PySide6.QtWidgets', fromlist=['QTableWidgetItem']).QTableWidgetItem(str(e.get("frame_number"))))
            
        proc_frames = d.get("process_frames", [])
        self._pt_data = {}
        for f in proc_frames:
            pid = f.get("pid")
            if pid is None: continue
            p = {
                "vpn": f.get("vpn"),
                "frame": f.get("index"),
                "valid": True,
                "referenced": f.get("referenced"),
                "modified": f.get("modified")
            }
            self._pt_data.setdefault(pid, []).append(p)
            
        # Bloquear señales para no disparar eventos espurios al limpiar
        self._pt_combo.blockSignals(True)
        self._pt_combo.clear()
        if self._pt_data:
            for pid in sorted(self._pt_data.keys()):
                self._pt_combo.addItem(f"Process {pid}", pid)
            
            # Restaurar señales y forzar la vista del primer proceso si se añadió alguno
            self._pt_combo.blockSignals(False)
            self._on_pt_combo_change(self._pt_combo.currentIndex())
        else:
            self._pt_combo.blockSignals(False)
            self._pt_table.setRowCount(0)
            
        swap = d.get("swap", {})
        max_p = swap.get("max_pages", 0)
        used_p = swap.get("used_pages", 0)
        self._swap_lbl.setText(f"Tamaño Total: {max_p * 4 / 1024.0:.1f} MB ({max_p} páginas)\nUsado: {used_p * 4 / 1024.0:.1f} MB ({used_p} páginas)\nLibre: {(max_p - used_p) * 4 / 1024.0:.1f} MB")

    def _on_pt_combo_change(self, idx: int):
        from PySide6.QtWidgets import QTableWidgetItem
        if idx < 0:
            self._pt_table.setRowCount(0)
            return
        pid = self._pt_combo.itemData(idx)
        entries = self._pt_data.get(pid, [])
        self._pt_table.setRowCount(len(entries))
        for i, p in enumerate(entries):
            self._pt_table.setItem(i, 0, QTableWidgetItem(str(p.get("vpn"))))
            self._pt_table.setItem(i, 1, QTableWidgetItem(str(p.get("frame"))))
            self._pt_table.setItem(i, 2, QTableWidgetItem("1" if p.get("valid") else "0"))
            self._pt_table.setItem(i, 3, QTableWidgetItem("1" if p.get("referenced") else "0"))
            self._pt_table.setItem(i, 4, QTableWidgetItem("1" if p.get("modified") else "0"))

    def update(self, segments: list | dict, stats: dict, mmu_table: dict = None, logs: list = None) -> None:  # type: ignore[override]
        """
        Refresh the memory visualizer.

        :param segments: list of segment dicts.
        :param stats:    stats dict (see class docstring).
        """
        if isinstance(segments, dict) and segments.get("type") == "PAGED":
            self._paged_data = segments
            self._btn_vm.setVisible(True)
            self._swap_bar.setVisible(True)
            self._mmu.setVisible(False)
            
            total_frames = segments.get("total_frames", 0)
            os_pages = segments.get("os_reserved_frames", 0)
            proc_frames = segments.get("process_frames", [])
            
            ram_segments = []
            if os_pages > 0:
                ram_segments.append({
                    "is_free": False, "pid": None, "segment_type": "os",
                    "size_mb": (os_pages * 4.0) / 1024.0, 
                    "label": f"OS Reserved ({os_pages} frames)"
                })
                
            curr_idx = os_pages
            used_pages = 0
            
            # Sort just in case, though backend should send them in order
            for f in sorted(proc_frames, key=lambda x: x.get("index", 0)):
                idx = f.get("index", 0)
                if idx > curr_idx:
                    free_count = idx - curr_idx
                    ram_segments.append({
                        "is_free": True, "pid": None, "segment_type": "free",
                        "size_mb": (free_count * 4.0) / 1024.0, 
                        "label": f"Free ({free_count} frames)"
                    })
                
                pid_val = f.get("pid")
                vpn = f.get("vpn", 0)
                seg_type = str(f.get("segment_type", "FREE")).lower()
                ram_segments.append({
                    "is_free": False, "pid": pid_val, "segment_type": seg_type,
                    "size_mb": 4.0 / 1024.0, 
                    "label": f"F{idx} (P{pid_val} VPN {vpn})"
                })
                used_pages += 1
                curr_idx = idx + 1
                
            if curr_idx < total_frames:
                free_count = total_frames - curr_idx
                ram_segments.append({
                    "is_free": True, "pid": None, "segment_type": "free",
                    "size_mb": (free_count * 4.0) / 1024.0, 
                    "label": f"Free ({free_count} frames)"
                })
                
            total_ram_mb = total_frames * 4.0 / 1024.0
            self._bar.set_segments(ram_segments, total_ram_mb, is_paged=True)
            
            swap = segments.get("swap", {})
            max_swap = swap.get("max_pages", 0)
            used_swap = swap.get("used_pages", 0)
            
            self._swap_bar.set_values(used_swap * 4.0 / 1024.0, max_swap * 4.0 / 1024.0)
            
            # Dinámicamente refrescar el inspector si está abierto
            if hasattr(self, "_vm_dialog") and self._vm_dialog.isVisible():
                self._refresh_vm_dialog()
            
            free_pages = total_frames - os_pages - used_pages
            self._set_val(self._s_frag, "0.0%")
            self._set_val(self._s_used, f"{used_pages * 4.0 / 1024.0:.1f} MB")
            self._set_val(self._s_free, f"{free_pages * 4.0 / 1024.0:.1f} MB")
            self._set_val(self._s_strat, f"VM Paginada ({os_pages * 4}KB OS)")
                
            return

        self._btn_vm.setVisible(False)
        self._swap_bar.setVisible(False)

        total_mb = float(stats.get("total_mb") or 1)
        self._bar.set_segments(segments if isinstance(segments, list) else [], total_mb, is_paged=False)

        # Stats cards
        used  = stats.get("used_mb", 0)
        free  = stats.get("free_mb", 0)
        frag  = stats.get("fragmentation")
        if frag is None:
            frag = stats.get("fragmentation_percent")
        if frag is None:
            frag = 0.0
        strat = stats.get("strategy", stats.get("allocation_strategy", "—"))

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
