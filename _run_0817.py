import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.argv = ["run_daily.py", "--date", "2026-08-17", "--no-send"]
runpy_file = str(Path(__file__).parent / "run_daily.py")
import runpy
runpy.run_path(runpy_file, run_name="__main__")
