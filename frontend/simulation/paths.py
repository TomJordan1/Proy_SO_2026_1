import os

# Directorio raíz del repositorio
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Directorio del motor C++ (y temporalmente, de los archivos compartidos)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

# TODO: En el futuro, cambiar SHARED_DATA_DIR a os.path.join(PROJECT_ROOT, "shared_data")
# cuando el motor en C++ esté configurado para leer de ahí.
SHARED_DATA_DIR = BACKEND_DIR

# Archivos de comunicación
ESCENARIO_PATH = os.path.join(SHARED_DATA_DIR, "escenario_modelo.json")
OUTPUT_PATH = os.path.join(SHARED_DATA_DIR, "output.json")

# Ejecutable del simulador
SIMULATOR_EXE = os.path.join(BACKEND_DIR, "simulator.exe")
