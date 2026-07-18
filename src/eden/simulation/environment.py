from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np

from eden.constants import Terrain, Weather
from eden.utilities.random_utils import smooth_field

if TYPE_CHECKING:
    from eden.config import Settings
    from eden.simulation.world import World


def generate_environment(settings: "Settings", rng: np.random.Generator) -> dict[str, np.ndarray]:
    shape = (settings.world.height, settings.world.width)
    broad = smooth_field(rng, shape, coarse=max(8, settings.world.width // 10))
    detail = smooth_field(rng, shape, coarse=max(4, settings.world.width // 24))
    elevation = np.clip(broad * 0.78 + detail * 0.22, 0.0, 1.0).astype(np.float32)
    wetness = smooth_field(rng, shape, coarse=max(7, settings.world.width // 14))
    water_line = float(np.quantile(elevation, 0.19))

    terrain = np.full(shape, Terrain.FERTILE, dtype=np.uint8)
    terrain[elevation <= water_line] = Terrain.WATER
    terrain[(elevation > 0.81) & (detail > 0.56)] = Terrain.ROCK
    dryness = (wetness < 0.37) & (terrain != Terrain.WATER) & (terrain != Terrain.ROCK)
    terrain[dryness] = Terrain.DRY

    water = np.zeros(shape, dtype=np.float32)
    water[terrain == Terrain.WATER] = np.clip(0.35 + (water_line - elevation[terrain == Terrain.WATER]) * 2.7, 0.35, 1.0)
    moisture = np.clip(wetness * 0.62 + water * 0.75, 0.0, 1.0).astype(np.float32)
    for _ in range(5):
        moisture = np.maximum(
            moisture,
            0.84
            * np.maximum.reduce(
                [np.roll(moisture, 1, 0), np.roll(moisture, -1, 0), np.roll(moisture, 1, 1), np.roll(moisture, -1, 1)]
            ),
        )
    fertility = np.clip(0.16 + 0.62 * wetness + 0.18 * (1.0 - elevation), 0.0, 1.0).astype(np.float32)
    fertility[terrain == Terrain.DRY] *= 0.42
    fertility[terrain == Terrain.ROCK] = 0.02
    plants = np.clip(fertility * moisture * (0.45 + detail * 0.5), 0.0, 0.88).astype(np.float32)
    plants[(terrain == Terrain.WATER) | (terrain == Terrain.ROCK)] = 0.0
    temperature = (18.0 - elevation * 11.0).astype(np.float32)
    sunlight = np.full(shape, 0.75, dtype=np.float32)
    signal = np.zeros(shape, dtype=np.float32)
    fire = np.zeros(shape, dtype=np.float32)
    ash = np.zeros(shape, dtype=np.float32)
    return {
        "terrain": terrain,
        "elevation": elevation,
        "water": water,
        "moisture": moisture,
        "fertility": fertility,
        "temperature": temperature,
        "sunlight": sunlight,
        "plants": plants,
        "signal": signal,
        "fire": fire,
        "ash": ash,
    }


def update_environment(world: "World", dt: float) -> None:
    sim = world.settings.simulation
    terrain = world.terrain

    day_phase = (world.tick % sim.ticks_per_day) / sim.ticks_per_day
    daylight = max(0.04, float(np.sin(day_phase * np.pi)))
    cloud_factor = 0.68 if world.weather in (Weather.CLOUDY, Weather.RAIN) else 1.0
    world.sunlight.fill(daylight * cloud_factor)

    season_angle = 2.0 * np.pi * ((world.tick % (sim.season_length_ticks * 4)) / (sim.season_length_ticks * 4))
    seasonal = float(np.sin(season_angle)) * 7.5
    weather_shift = 0.0
    if world.weather == Weather.HEATWAVE:
        weather_shift = 8.5
    elif world.weather == Weather.COLD:
        weather_shift = -9.0
    world.temperature[:] = 18.0 - world.elevation * 11.0 + seasonal + weather_shift + world.temperature_modifier

    if world.weather == Weather.RAIN:
        soil = terrain != Terrain.ROCK
        world.moisture[soil] = np.clip(world.moisture[soil] + 0.030 * dt, 0.0, 1.0)
        water_cells = terrain == Terrain.WATER
        world.water[water_cells] = np.clip(world.water[water_cells] + 0.014 * dt, 0.0, 1.0)
    elif world.weather == Weather.DROUGHT:
        world.moisture[:] = np.clip(world.moisture - 0.006 * dt, 0.0, 1.0)
        world.water[:] = np.clip(world.water - 0.0015 * dt, 0.0, 1.0)
    else:
        evaporation = (0.00055 + max(0.0, seasonal) * 0.00004) * dt
        world.moisture[:] = np.clip(world.moisture - evaporation, 0.0, 1.0)

    water_influence = np.maximum.reduce(
        [world.water, np.roll(world.water, 1, 0), np.roll(world.water, -1, 0), np.roll(world.water, 1, 1), np.roll(world.water, -1, 1)]
    )
    world.moisture[:] = np.clip(world.moisture + water_influence * 0.006 * dt, 0.0, 1.0)

    comfort = np.clip(1.0 - np.abs(world.temperature - 19.0) / 24.0, 0.0, 1.0)
    suitability = world.sunlight * world.moisture * world.fertility * comfort * (1.0 - world.ash * 0.65)
    neighbor_plants = (
        np.roll(world.plants, 1, 0)
        + np.roll(world.plants, -1, 0)
        + np.roll(world.plants, 1, 1)
        + np.roll(world.plants, -1, 1)
    ) * 0.25
    growth = sim.plant_growth_rate * suitability * world.plants * (1.0 - world.plants) * dt
    spread = sim.plant_spread_rate * suitability * neighbor_plants * (1.0 - world.plants) * dt
    seed_bank = 0.00008 * suitability * dt
    stress = np.clip(0.14 - suitability, 0.0, 0.14) * 0.015 * dt
    world.plants[:] = np.clip(world.plants + growth + spread + seed_bank - stress, 0.0, 1.0)
    world.plants[(terrain == Terrain.WATER) | (terrain == Terrain.ROCK)] = 0.0

    _update_fire(world, dt)
    world.signal[:] *= max(0.0, 1.0 - 0.55 * dt)
    world.ash[:] = np.clip(world.ash - 0.0008 * dt, 0.0, 1.0)


def _update_fire(world: "World", dt: float) -> None:
    burning = world.fire > 0.03
    if not bool(burning.any()):
        world.fire.fill(0.0)
        return
    neighbors = np.maximum.reduce(
        [np.roll(world.fire, 1, 0), np.roll(world.fire, -1, 0), np.roll(world.fire, 1, 1), np.roll(world.fire, -1, 1)]
    )
    chance = np.clip(neighbors * world.plants * (1.0 - world.moisture) * 0.30 * dt, 0.0, 0.8)
    ignitable = (~burning) & (world.plants > 0.12) & (world.terrain != Terrain.WATER) & (world.terrain != Terrain.ROCK)
    newly_burning = ignitable & (world.rng.random(world.fire.shape) < chance)
    world.fire[newly_burning] = np.maximum(world.fire[newly_burning], 0.42)
    consumed = np.minimum(world.plants, world.fire * 0.22 * dt)
    world.plants[:] -= consumed
    world.ash[:] = np.clip(world.ash + consumed * 0.65, 0.0, 1.0)
    decay = (0.16 + (world.plants < 0.04) * 0.34 + world.moisture * 0.45) * dt
    world.fire[:] = np.clip(world.fire - decay, 0.0, 1.0)
    world.fire[newly_burning] = np.maximum(world.fire[newly_burning], 0.42)
