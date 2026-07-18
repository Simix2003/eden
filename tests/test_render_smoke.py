from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from eden.app import EdenApp
from eden.persistence.repository import WorldRepository
from eden.simulation.world import World


def test_real_pygame_frame_renders_headlessly(settings, tmp_path) -> None:
    settings.ui.width = 960
    settings.ui.height = 640
    settings.persistence.database_path = "render-test.db"
    world = World(settings, seed=25)
    repository = WorldRepository(settings, tmp_path)
    app = EdenApp(settings, world, repository)
    try:
        app.selected_id = min(world.organisms)
        app._draw()
        assert app.screen.get_size() == (960, 640)
        assert app.screen.get_at((10, 10)) != pygame.Color(0, 0, 0, 255)
    finally:
        pygame.quit()

