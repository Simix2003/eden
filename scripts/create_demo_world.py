from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from eden.config import load_settings
from eden.persistence.repository import WorldRepository
from eden.simulation.world import World


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a real, deterministic EDEN demo world")
    parser.add_argument("--seed", type=int, default=314159)
    parser.add_argument("--ticks", type=int, default=320)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "saves" / "eden.db")
    args = parser.parse_args()
    settings = load_settings()
    settings.persistence.database_path = str(args.output.resolve())
    world = World(settings, seed=args.seed)
    world.run(max(0, args.ticks))
    repository = WorldRepository(settings, ROOT)
    archived = repository.archive_for_new_world()
    repository.save(world)
    print(f"Created demo world at {repository.path}")
    print(f"seed={world.seed} tick={world.tick} population={len(world.organisms)} hash={world.state_hash()[:16]}")
    if archived:
        print(f"Archived the previous world at {archived}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

