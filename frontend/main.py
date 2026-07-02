"""
main.py — Punto de entrada de PatatOS v2.

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

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from PySide6.QtGui import QFont

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
    from simulation.paths import SHARED_DATA_DIR, OUTPUT_PATH
    if not os.path.exists(SHARED_DATA_DIR):
        os.makedirs(SHARED_DATA_DIR, exist_ok=True)

    while True:
        dlg = ConfigDialog()
        if dlg.exec() != QDialog.DialogCode.Accepted:
            break

        # El diálogo ha creado "escenario_modelo.json" y fingió ejecutar C++.
        # Ahora deberíamos tener "output_modelo.json".
        output_file = OUTPUT_PATH
        if not os.path.exists(output_file):
            QMessageBox.critical(None, "Error", f"No se encontró el archivo {output_file} generado por el backend.")
            break

        # ── Clock + Ventana ───────────────────────────────────────────────────────
        import json
        speed_ms = 800
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if len(data.get("ticks", [])) > 0:
                    pass
        except Exception as e:
            print(f"Error comprobando JSON en main: {e}")

        clock = SimClock(speed_ms=speed_ms)
        window = MainWindow(output_file, clock)
        window._wants_restart = False
        window.show()

        app.exec()
        
        if not getattr(window, '_wants_restart', False):
            break

    sys.exit(0)


if __name__ == "__main__":
    main()
