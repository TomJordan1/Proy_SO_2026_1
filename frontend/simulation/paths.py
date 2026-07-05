import os
import sys

# Directorio raíz del repositorio
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Directorio del motor C++ (y temporalmente, de los archivos compartidos)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

# TODO: En el futuro, cambiar SHARED_DATA_DIR a os.path.join(PROJECT_ROOT, "shared_data")
# cuando el motor en C++ esté configurado para leer de ahí.
SHARED_DATA_DIR = os.path.join(PROJECT_ROOT, "shared_data")

# Archivos de comunicación
ESCENARIO_PATH = os.path.join(SHARED_DATA_DIR, "input.json")
OUTPUT_PATH = os.path.join(SHARED_DATA_DIR, "output.json")

# Ejecutable del simulador
exe_extension = ".exe" if sys.platform == "win32" else ""
SIMULATOR_EXE = os.path.join(BACKEND_DIR, f"simulator{exe_extension}")
