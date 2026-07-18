from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from eden.config import load_settings
from eden.simulation.world import World
from eden.utilities.profiling import memory_mb


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EDEN's bounded headless stability validation")
    parser.add_argument("--steps", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=314159)
    args = parser.parse_args()
    if args.steps <= 0:
        raise SystemExit("--steps must be positive")
    settings = load_settings()
    world = World(settings, seed=args.seed)
    start_memory = memory_mb()
    populations = [len(world.organisms)]
    event_peak = len(world.events.events)
    started = time.perf_counter()
    for completed in range(0, args.steps, 100):
        world.run(min(100, args.steps - completed))
        world.validate_full()
        populations.append(len(world.organisms))
        event_peak = max(event_peak, len(world.events.events))
    elapsed = time.perf_counter() - started
    result = {
        "steps": args.steps,
        "elapsed_seconds": elapsed,
        "ticks_per_second": args.steps / elapsed,
        "seed": args.seed,
        "world_size": f"{world.shape[1]}x{world.shape[0]}",
        "initial_population": populations[0],
        "minimum_population": min(populations),
        "maximum_population": max(populations),
        "final_population": populations[-1],
        "population_cap": settings.world.maximum_population,
        "events_peak": event_peak,
        "events_cap": settings.simulation.event_limit,
        "metrics_count": len(world.metrics),
        "metrics_cap": settings.simulation.metric_limit,
        "memory_start_mb": start_memory,
        "memory_end_mb": memory_mb(),
        "state_hash": world.state_hash(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "validated": True,
    }
    path = ROOT / "data" / "logs" / "long_run_results.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved long-run result to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

