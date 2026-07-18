from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    checks.append(("Python 3.11+", sys.version_info >= (3, 11), sys.version.split()[0]))
    checks.append(("64-bit runtime", struct.calcsize("P") == 8, f"{struct.calcsize('P') * 8}-bit"))
    try:
        import numpy

        checks.append(("NumPy", True, numpy.__version__))
    except Exception as exc:
        checks.append(("NumPy", False, str(exc)))
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    try:
        import pygame

        pygame.init()
        pygame.display.set_mode((64, 64))
        pygame.display.quit()
        checks.append(("pygame-ce / SDL", True, pygame.version.ver))
    except Exception as exc:
        checks.append(("pygame-ce / SDL", False, str(exc)))
    try:
        from eden.config import load_settings
        from eden.persistence.repository import WorldRepository
        from eden.simulation.world import World

        settings = load_settings()
        settings.world.width = settings.world.height = 40
        settings.world.initial_population = 12
        settings.world.maximum_population = 30
        settings.persistence.database_path = "eden-install-check.db"
        with tempfile.TemporaryDirectory() as directory:
            world = World(settings, seed=101)
            world.run(12)
            expected = world.state_hash()
            repository = WorldRepository(settings, Path(directory))
            repository.save(world, now=1000.0)
            restored = repository.load_latest()
            checks.append(("simulation + SQLite", expected == restored.state_hash(), f"tick {restored.tick}"))
    except Exception as exc:
        checks.append(("simulation + SQLite", False, str(exc)))
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL':4}  {name:22} {detail}")
    failed = [name for name, passed, _ in checks if not passed]
    if failed:
        print("Installation verification failed: " + ", ".join(failed))
        return 1
    print("EDEN installation verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

