import os, re
path = r'ui/main_window.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add import at the top
if 'from simulation.paths import' not in content:
    content = content.replace('import json', 'import json\nimport subprocess\nfrom simulation.paths import ESCENARIO_PATH, OUTPUT_PATH, BACKEND_DIR, SIMULATOR_EXE', 1)

content = content.replace('"escenario_modelo.json"', 'ESCENARIO_PATH')
content = content.replace('"output_modelo.json"', 'OUTPUT_PATH')

pattern = re.compile(r'for i in range\(101\):.*?(?:time\.sleep\([^)]+\)\s*)+pd\.close\(\)', re.DOTALL)
replacement = '''process = subprocess.Popen([SIMULATOR_EXE], cwd=BACKEND_DIR)
        while process.poll() is None:
            QCoreApplication.processEvents()
            time.sleep(0.05)
        pd.close()
        if process.returncode != 0:
            QMessageBox.critical(self, "Error de Backend", f"El motor C++ terminó con error: {process.returncode}")
            return'''
content = pattern.sub(replacement, content)

content = re.compile(r'(pd\s*=\s*QProgressDialog\([^)]*?,)\s*0,\s*100,').sub(r'\1 0, 0,', content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Refactored main_window.py')
