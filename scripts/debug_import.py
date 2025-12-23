import importlib
import traceback
import os
import sys

# Asegurar que la raíz del proyecto está en sys.path cuando se ejecuta
# este script desde scripts/. Así `import app` funcionará.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    importlib.import_module("app.main")
    print("app.main import OK")
except Exception:
    traceback.print_exc()
    raise
