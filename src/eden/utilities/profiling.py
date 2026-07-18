from __future__ import annotations

from dataclasses import dataclass
import os
import time


@dataclass(slots=True)
class BenchmarkResult:
    steps: int
    elapsed_seconds: float
    ticks_per_second: float
    population: int
    world_size: str
    memory_mb: float | None


def memory_mb() -> float | None:
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        return None


def benchmark_world(world: object, steps: int) -> BenchmarkResult:
    start = time.perf_counter()
    world.run(steps)  # type: ignore[attr-defined]
    elapsed = time.perf_counter() - start
    return BenchmarkResult(
        steps=steps,
        elapsed_seconds=elapsed,
        ticks_per_second=steps / max(elapsed, 1e-9),
        population=len(world.organisms),  # type: ignore[attr-defined]
        world_size=f"{world.shape[1]}x{world.shape[0]}",  # type: ignore[attr-defined]
        memory_mb=memory_mb(),
    )

