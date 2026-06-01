"""
main.py — Punto de entrada de PatatOS.

Flujo:
    1. QApplication
    2. ConfigDialog → HardwareConfig
    3. SimulationEngine(config)
    4. Si modo manual → crear procesos en el engine
    5. SimClock(speed)
    6. MainWindow(engine, clock).show()
    7. app.exec()
"""
from __future__ import annotations

import sys
import os
import warnings

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtGui import QFont

from simulation.config import HardwareConfig
from simulation.engine import SimulationEngine, build_scheduler
from simulation.clock import SimClock
from ui.config_dialog import ConfigDialog
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PatatOS")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Universidad — Simulación SO")
    app.setFont(QFont("Segoe UI", 10))

    # ── Configuración inicial ─────────────────────────────────────────────────
    dlg = ConfigDialog()
    if dlg.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)

    config, manual_procs = dlg.get_config()

    # ── Engine ────────────────────────────────────────────────────────────────
    # Suprimir warning de MLFQ si está seleccionado
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        engine = SimulationEngine(config)

    # Crear procesos manuales si aplica
    for pd in manual_procs:
        engine.create_process(
            name=pd.get("name"),
            burst_time=pd.get("burst_time", 20),
            priority=pd.get("priority", 5),
            memory_size=pd.get("memory_size", 32),
            process_type=pd.get("process_type", "CPU_BOUND"),
        )

    # ── Clock + Ventana ───────────────────────────────────────────────────────
    clock = SimClock(speed_ms=config.sim_speed_ms)
    window = MainWindow(engine, clock)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
