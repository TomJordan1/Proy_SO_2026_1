"""
ui/styles.py — Sistema de diseño visual de PatatOS.

Tema oscuro premium con paleta de colores coherente.
Los colores se exportan como constantes para uso en widgets.
"""
from __future__ import annotations


class Colors:
    # Fondos
    BG_BASE       = "#0d1117"
    BG_SURFACE    = "#161b22"
    BG_ELEVATED   = "#21262d"
    BG_CARD       = "#1c2128"

    # Texto
    TEXT_PRIMARY  = "#e6edf3"
    TEXT_SEC      = "#8b949e"
    TEXT_MUTED    = "#484f58"

    # Acento principal (púrpura/índigo)
    ACCENT        = "#7c3aed"
    ACCENT_LIGHT  = "#a78bfa"
    ACCENT_DARK   = "#5b21b6"

    # Estados de proceso
    STATE_NEW        = "#0891b2"   # cyan
    STATE_READY      = "#16a34a"   # verde
    STATE_RUNNING    = "#7c3aed"   # púrpura
    STATE_WAITING    = "#d97706"   # naranja
    STATE_TERMINATED = "#374151"   # gris oscuro
    STATE_ERROR      = "#dc2626"   # rojo

    # Tipos de proceso
    TYPE_CPU_BOUND   = "#6366f1"   # índigo
    TYPE_IO_BOUND    = "#06b6d4"   # cyan
    TYPE_INTERACTIVE = "#10b981"   # esmeralda
    TYPE_SYSTEM      = "#f59e0b"   # ámbar

    # Memoria
    MEM_OS    = "#374151"
    MEM_TEXT  = "#4f46e5"
    MEM_DATA  = "#0891b2"
    MEM_HEAP  = "#059669"
    MEM_STACK = "#d97706"
    MEM_FREE  = "#1c2128"

    # Borders
    BORDER    = "#30363d"
    BORDER_ACTIVE = "#7c3aed"

    # Gráficos
    CHART_GRID = "#21262d"

    # CPU cores (hasta 4)
    CORE_COLORS = ["#7c3aed", "#0891b2", "#16a34a", "#d97706"]

    # Severity del log
    LOG_INFO    = "#8b949e"
    LOG_READY   = "#16a34a"
    LOG_RUNNING = "#a78bfa"
    LOG_WAITING = "#d97706"
    LOG_TERM    = "#374151"
    LOG_ERROR   = "#f87171"


# ── Estado → Color ─────────────────────────────────────────────────────────────
STATE_COLORS = {
    "NEW":        Colors.STATE_NEW,
    "READY":      Colors.STATE_READY,
    "RUNNING":    Colors.STATE_RUNNING,
    "WAITING":    Colors.STATE_WAITING,
    "TERMINATED": Colors.STATE_TERMINATED,
}

TYPE_COLORS = {
    "CPU_BOUND":   Colors.TYPE_CPU_BOUND,
    "IO_BOUND":    Colors.TYPE_IO_BOUND,
    "INTERACTIVE": Colors.TYPE_INTERACTIVE,
    "SYSTEM":      Colors.TYPE_SYSTEM,
}

# Color determinístico por PID (para barras de memoria)
def pid_color(pid: int) -> str:
    palette = [
        "#7c3aed", "#0891b2", "#16a34a", "#d97706",
        "#dc2626", "#db2777", "#059669", "#2563eb",
        "#9333ea", "#0284c7", "#65a30d", "#ea580c",
    ]
    return palette[pid % len(palette)]


def get_main_stylesheet() -> str:
    """QSS global de la aplicación."""
    c = Colors
    return f"""
    /* ── Base ── */
    QWidget {{
        background-color: {c.BG_BASE};
        color: {c.TEXT_PRIMARY};
        font-family: 'Segoe UI', 'Inter', sans-serif;
        font-size: 10pt;
    }}
    QMainWindow, QDialog {{
        background-color: {c.BG_BASE};
    }}

    /* ── GroupBox ── */
    QGroupBox {{
        border: 1px solid {c.BORDER};
        border-radius: 6px;
        margin-top: 14px;
        padding: 8px 6px 6px 6px;
        background-color: {c.BG_SURFACE};
        color: {c.TEXT_PRIMARY};
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        top: 0px;
        padding: 0 4px;
        color: {c.ACCENT_LIGHT};
        font-size: 9pt;
    }}

    /* ── Labels ── */
    QLabel {{ background: transparent; }}

    /* ── Buttons ── */
    QPushButton {{
        background-color: {c.BG_ELEVATED};
        border: 1px solid {c.BORDER};
        border-radius: 5px;
        padding: 5px 12px;
        color: {c.TEXT_PRIMARY};
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {c.ACCENT_DARK};
        border-color: {c.ACCENT_LIGHT};
        color: white;
    }}
    QPushButton#btn_start {{
        background-color: {c.ACCENT};
        border-color: {c.ACCENT_LIGHT};
        color: white;
        font-weight: 700;
    }}
    QPushButton#btn_start:hover {{
        background-color: {c.ACCENT_LIGHT};
        color: {c.BG_BASE};
    }}
    QPushButton#btn_pause {{
        background-color: {c.BG_ELEVATED};
        border-color: {c.STATE_WAITING};
        color: {c.STATE_WAITING};
    }}
    QPushButton#btn_reset {{
        background-color: {c.BG_ELEVATED};
        border-color: {c.BORDER};
        color: {c.TEXT_SEC};
    }}

    /* ── Inputs ── */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {c.BG_ELEVATED};
        border: 1px solid {c.BORDER};
        border-radius: 4px;
        padding: 4px 8px;
        color: {c.TEXT_PRIMARY};
        selection-background-color: {c.ACCENT};
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border-color: {c.ACCENT_LIGHT};
    }}
    QComboBox::drop-down {{ border: none; }}
    QComboBox QAbstractItemView {{
        background-color: {c.BG_ELEVATED};
        border: 1px solid {c.BORDER};
        selection-background-color: {c.ACCENT};
    }}

    /* ── Tables ── */
    QTableWidget {{
        background-color: {c.BG_SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: 4px;
        gridline-color: {c.BORDER};
        selection-background-color: {c.ACCENT_DARK};
    }}
    QTableWidget::item {{ padding: 4px 6px; }}
    QHeaderView::section {{
        background-color: {c.BG_ELEVATED};
        border: none;
        border-bottom: 1px solid {c.BORDER};
        border-right: 1px solid {c.BORDER};
        padding: 5px 8px;
        color: {c.TEXT_SEC};
        font-weight: 600;
        font-size: 9pt;
    }}

    /* ── ScrollBar ── */
    QScrollBar:vertical {{
        background: {c.BG_BASE};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {c.BORDER};
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {c.ACCENT}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    QScrollBar:horizontal {{
        background: {c.BG_BASE};
        height: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c.BORDER};
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {c.ACCENT}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

    /* ── TabBar ── */
    QTabWidget::pane {{
        border: 1px solid {c.BORDER};
        border-radius: 4px;
        background-color: {c.BG_SURFACE};
    }}
    QTabBar::tab {{
        background: {c.BG_ELEVATED};
        border: 1px solid {c.BORDER};
        border-bottom: none;
        padding: 6px 14px;
        margin-right: 2px;
        border-radius: 4px 4px 0 0;
        color: {c.TEXT_SEC};
    }}
    QTabBar::tab:selected {{
        background: {c.BG_SURFACE};
        color: {c.ACCENT_LIGHT};
        border-color: {c.BORDER};
        border-bottom: 1px solid {c.BG_SURFACE};
    }}
    QTabBar::tab:hover:!selected {{ color: {c.TEXT_PRIMARY}; }}

    /* ── Slider ── */
    QSlider::groove:horizontal {{
        height: 4px;
        background: {c.BG_ELEVATED};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {c.ACCENT_LIGHT};
        width: 14px; height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider::sub-page:horizontal {{ background: {c.ACCENT}; border-radius: 2px; }}

    /* ── ToolBar ── */
    QToolBar {{
        background: {c.BG_BASE};
        border-bottom: 1px solid {c.BORDER};
        spacing: 4px;
        padding: 4px;
    }}
    QToolBar QLabel {{ padding: 0 4px; }}

    /* ── StatusBar ── */
    QStatusBar {{
        background: {c.BG_BASE};
        border-top: 1px solid {c.BORDER};
        color: {c.TEXT_SEC};
        font-size: 8pt;
    }}

    /* ── Separadores ── */
    QFrame[frameShape="4"], QFrame[frameShape="5"] {{
        color: {c.BORDER};
        background-color: {c.BORDER};
    }}
    """
