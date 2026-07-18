from __future__ import annotations

import numpy as np

from eden.constants import Terrain, Weather
from eden.simulation.environment import update_environment
from eden.simulation.world import World


def test_procedural_generation_is_deterministic(settings) -> None:
    first = World(settings, seed=90210, populate=False)
    second = World(settings, seed=90210, populate=False)
    assert np.array_equal(first.terrain, second.terrain)
    assert np.array_equal(first.elevation, second.elevation)
    assert first.state_hash() == second.state_hash()


def test_terrain_and_environment_ranges(settings) -> None:
    world = World(settings, seed=3)
    world.validate_full()
    assert set(np.unique(world.terrain)).issubset({int(item) for item in Terrain})
    assert np.any(world.terrain == Terrain.WATER)
    assert np.any(world.terrain == Terrain.FERTILE)
    assert np.any(world.terrain == Terrain.DRY)
    assert np.any(world.terrain == Terrain.ROCK)


def test_plants_grow_and_die_under_controlled_conditions(settings) -> None:
    world = World(settings, seed=4, populate=False)
    soil = world.terrain == Terrain.FERTILE
    world.tick = settings.simulation.ticks_per_day // 2
    world.weather = Weather.CLEAR
    world.plants[soil] = 0.22
    world.moisture[soil] = 1.0
    world.fertility[soil] = 1.0
    world.temperature_modifier = 1.0
    before = float(world.plants[soil].mean())
    update_environment(world, 4.0)
    assert float(world.plants[soil].mean()) > before
    world.moisture[soil] = 0.0
    world.fertility[soil] = 0.0
    before_stress = float(world.plants[soil].mean())
    for _ in range(12):
        update_environment(world, 4.0)
    assert float(world.plants[soil].mean()) < before_stress


def test_rain_and_drought_change_moisture(settings) -> None:
    world = World(settings, seed=5, populate=False)
    world.moisture.fill(0.5)
    world.weather = Weather.RAIN
    update_environment(world, 1.0)
    rainy = float(world.moisture.mean())
    world.weather = Weather.DROUGHT
    update_environment(world, 1.0)
    assert float(world.moisture.mean()) < rainy


def test_fire_spreads_and_expires(settings) -> None:
    world = World(settings, seed=6, populate=False)
    world.terrain.fill(Terrain.FERTILE)
    world.plants.fill(0.9)
    world.moisture.fill(0.0)
    center = (settings.world.height // 2, settings.world.width // 2)
    world.fire[center] = 1.0
    for _ in range(8):
        update_environment(world, 1.0)
    assert int((world.ash > 0).sum()) > 1
    world.plants.fill(0.0)
    for _ in range(8):
        update_environment(world, 1.0)
    assert float(world.fire.max()) == 0.0


def test_interventions_have_mechanical_effects(settings) -> None:
    world = World(settings, seed=7)
    x = y = settings.world.width // 2
    before = float(world.moisture.mean())
    assert world.apply_intervention("rain", x, y, 6)
    assert float(world.moisture.mean()) > before
    assert world.apply_intervention("fire", x, y, 12)
    assert float(world.fire.max()) > 0
    assert world.interventions[-1]["kind"] == "fire"

