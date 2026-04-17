import sys
import runpy
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Importing this module executes the Streamlit editor app definition.
runpy.run_module("epicc.editor.__main__", run_name="__main__")
