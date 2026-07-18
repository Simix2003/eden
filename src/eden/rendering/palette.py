from __future__ import annotations

import numpy as np

from eden.constants import Terrain

INK = (225, 232, 224)
MUTED = (139, 151, 143)
PANEL = (14, 19, 18)
PANEL_ALT = (20, 27, 24)
BACKGROUND = (6, 9, 9)
ACCENT = (196, 226, 122)
WARNING = (241, 150, 87)
WATER = (54, 103, 120)


def world_rgb(world: object) -> np.ndarray:
    terrain = world.terrain  # type: ignore[attr-defined]
    height, width = terrain.shape
    rgb = np.zeros((height, width, 3), dtype=np.float32)
    rgb[terrain == Terrain.WATER] = (27, 61, 75)
    rgb[terrain == Terrain.FERTILE] = (49, 64, 48)
    rgb[terrain == Terrain.DRY] = (83, 70, 46)
    rgb[terrain == Terrain.ROCK] = (63, 67, 64)

    elevation = world.elevation[..., None]  # type: ignore[attr-defined]
    rgb *= 0.78 + elevation * 0.35
    plants = world.plants[..., None]  # type: ignore[attr-defined]
    green = np.zeros_like(rgb)
    green[..., 0] = 49
    green[..., 1] = 116
    green[..., 2] = 65
    rgb = rgb * (1.0 - plants * 0.72) + green * plants * 0.72
    water = world.water[..., None]  # type: ignore[attr-defined]
    water_color = np.zeros_like(rgb)
    water_color[..., :] = (39, 112, 135)
    water_mask = (terrain == Terrain.WATER)[..., None]
    rgb = np.where(water_mask, rgb * (1.0 - water * 0.45) + water_color * water * 0.45, rgb)
    ash = world.ash[..., None]  # type: ignore[attr-defined]
    rgb *= 1.0 - ash * 0.52
    fire = world.fire[..., None]  # type: ignore[attr-defined]
    flame = np.zeros_like(rgb)
    flame[..., :] = (255, 111, 35)
    rgb = rgb * (1.0 - fire * 0.82) + flame * fire * 0.82
    light = float(world.sunlight.mean())  # type: ignore[attr-defined]
    rgb *= 0.52 + light * 0.62
    return np.clip(rgb, 0, 255).astype(np.uint8)

