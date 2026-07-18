from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
raise SystemExit(subprocess.call([sys.executable, str(ROOT / "run.py"), "--benchmark", *sys.argv[1:]], cwd=ROOT))

