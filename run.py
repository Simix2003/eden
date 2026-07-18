from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
import os
from pathlib import Path
import platform
import signal
import sys
import time

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eden.config import load_settings
from eden.persistence.repository import WorldRepository, perform_offline_catchup
from eden.simulation.world import World
from eden.utilities.logging_setup import configure_logging
from eden.utilities.profiling import benchmark_world

LOGGER = logging.getLogger("eden")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EDEN — a persistent artificial ecosystem")
    parser.add_argument("--fullscreen", action="store_true", help="open the living display in fullscreen")
    parser.add_argument("--headless", action="store_true", help="run the ecosystem without a graphical display")
    parser.add_argument("--new-world", action="store_true", help="archive the current save and deliberately create a fresh world")
    parser.add_argument("--seed", type=int, help="create a fresh world with this deterministic seed")
    parser.add_argument("--benchmark", action="store_true", help="run a representative headless benchmark and exit")
    parser.add_argument("--safe-mode", action="store_true", help="use conservative rendering settings")
    parser.add_argument("--steps", type=int, help="headless ticks to run before saving and exiting; omit to run continuously")
    parser.add_argument("--config", type=Path, help="path to a TOML configuration file")
    parser.add_argument("--no-catchup", action="store_true", help="skip offline catch-up for this launch")
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    return parser


def load_or_create(settings: object, repository: WorldRepository, fresh: bool, seed: int | None) -> World:
    if fresh or seed is not None:
        archived = repository.archive_for_new_world()
        if archived:
            LOGGER.info("Archived previous world at %s", archived)
        return World(settings, seed=seed)
    if repository.has_save():
        try:
            return repository.load_latest()
        except Exception:
            LOGGER.exception("All complete snapshots were invalid; retaining the database and starting a recoverable new world")
    return World(settings)


def run_headless(world: World, repository: WorldRepository, steps: int | None, catch_up: bool) -> int:
    if catch_up:
        result = perform_offline_catchup(
            world,
            progress=lambda current, total: print(f"\rOffline catch-up {current:>5}/{total}", end="", flush=True),
        )
        if result.steps:
            print()
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)
    completed = 0
    last_save = time.monotonic()
    try:
        while not stopping and (steps is None or completed < steps):
            batch = 1 if steps is not None else settings_batch(world)
            if steps is not None:
                batch = min(batch, steps - completed)
            world.run(batch)
            completed += batch
            if time.monotonic() - last_save >= world.settings.persistence.save_interval_seconds:
                repository.save(world)
                last_save = time.monotonic()
    finally:
        repository.save(world)
    print(f"EDEN headless: tick={world.tick} population={len(world.organisms)} hash={world.state_hash()[:16]}")
    return 0


def settings_batch(world: World) -> int:
    return max(1, world.settings.simulation.tick_rate)


def run_benchmark(settings: object, seed: int | None) -> int:
    world = World(settings, seed=seed)
    result = benchmark_world(world, 1500)
    render_fps, render_driver = benchmark_render(world, settings, 120)
    output = {
        **asdict(result),
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "operating_system": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "not reported",
        "seed": world.seed,
        "final_tick": world.tick,
        "state_hash": world.state_hash(),
        "render_fps": render_fps,
        "render_driver": render_driver,
        "note": "Development-computer result; Raspberry Pi 5 performance requires on-device verification.",
    }
    path = ROOT / "data" / "logs" / "benchmark_results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    print(f"Saved benchmark to {path}")
    return 0


def benchmark_render(world: World, settings: object, frames: int) -> tuple[float | None, str]:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    try:
        import pygame
        from eden.rendering.camera import Camera
        from eden.rendering.renderer import WorldRenderer
        from eden.ui.layout import calculate_layout

        pygame.init()
        screen = pygame.display.set_mode((1280, 720))
        layout = calculate_layout(screen.get_size(), True)
        camera = Camera(world.shape[1], world.shape[0], layout.world)
        renderer = WorldRenderer(settings.ui.performance_mode)
        start = time.perf_counter()
        for _ in range(frames):
            renderer.draw(screen, world, camera, selected_id=None, preview=None)
            pygame.display.flip()
        elapsed = time.perf_counter() - start
        driver = pygame.display.get_driver()
        pygame.quit()
        return frames / max(elapsed, 1e-9), driver
    except Exception as exc:
        LOGGER.warning("Render benchmark was unavailable: %s", exc)
        return None, f"unavailable: {exc}"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.steps is not None and args.steps < 0:
        raise SystemExit("--steps must be non-negative")
    settings = load_settings(args.config)
    if args.safe_mode:
        settings.ui.performance_mode = "low"
        settings.ui.render_fps = min(settings.ui.render_fps, 20)
    configure_logging(ROOT / "data" / "logs", args.verbose)
    if args.benchmark:
        return run_benchmark(settings, args.seed)
    repository = WorldRepository(settings, ROOT)
    world = load_or_create(settings, repository, args.new_world, args.seed)
    if args.headless:
        return run_headless(world, repository, args.steps, not args.no_catchup)
    from eden.app import EdenApp

    app = EdenApp(settings, world, repository, fullscreen=args.fullscreen or settings.ui.fullscreen)
    return app.run(catch_up=not args.no_catchup)


if __name__ == "__main__":
    raise SystemExit(main())
