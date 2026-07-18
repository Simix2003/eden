from __future__ import annotations

import math

from eden.constants import Terrain
from eden.simulation.world import World


def test_eating_and_drinking_use_real_resources(settings) -> None:
    world = World(settings, seed=8)
    organism = next(iter(world.organisms.values()))
    x, y = int(organism.x), int(organism.y)
    world.plants[y, x] = 0.8
    organism.energy = 10.0
    newborns = []
    before_plant = float(world.plants[y, x])
    world._apply_action(organism, 3, 1.0, newborns)
    assert organism.energy > 10.0
    assert world.plants[y, x] < before_plant
    organism.hydration = 10.0
    world.water[max(0, y - 1) : y + 2, max(0, x - 1) : x + 2] = 0.5
    world._apply_action(organism, 4, 1.0, newborns)
    assert organism.hydration > 10.0


def test_movement_rejects_rock(settings) -> None:
    world = World(settings, seed=9)
    organism = next(iter(world.organisms.values()))
    organism.x, organism.y = 10.2, 10.2
    organism.orientation = 0.0
    world.terrain[10, 11] = Terrain.ROCK
    before = (organism.x, organism.y)
    world._apply_action(organism, 0, 1.0, [])
    assert (organism.x, organism.y) == before


def test_reproduction_produces_bounded_valid_child(settings) -> None:
    world = World(settings, seed=10)
    parent = next(iter(world.organisms.values()))
    parent.age = settings.evolution.minimum_reproduction_age_seconds + 1
    parent.energy = parent.genome.traits["max_energy"]
    parent.reproduction_cooldown = 0
    initial_ids = set(world.organisms)
    for _ in range(20):
        world.step()
        if set(world.organisms) - initial_ids:
            break
        parent.energy = parent.genome.traits["max_energy"]
        parent.reproduction_cooldown = 0
    child_ids = set(world.organisms) - initial_ids
    assert child_ids
    child = world.organisms[min(child_ids)]
    assert child.parent_id is not None
    assert child.generation >= 1
    assert 0 <= child.x < world.shape[1] and 0 <= child.y < world.shape[0]
    assert len(world.organisms) <= settings.world.maximum_population


def test_death_cause_is_recorded(settings) -> None:
    world = World(settings, seed=11)
    organism = next(iter(world.organisms.values()))
    organism.age = organism.genome.traits["lifespan"] + 1
    organism_id = organism.organism_id
    world.step()
    assert organism_id not in world.organisms
    assert world.death_records[-1]["cause"] == "old age"


def test_population_cap_is_never_exceeded(settings) -> None:
    settings.world.maximum_population = settings.world.initial_population
    world = World(settings, seed=12)
    assert world.spawn_organism() is None
    world.run(100)
    assert len(world.organisms) <= settings.world.maximum_population


def test_choose_and_bless_are_mortal_statuses(settings) -> None:
    world = World(settings, seed=13)
    organism = next(iter(world.organisms.values()))
    assert world.choose(organism.organism_id)
    assert world.bless(organism.organism_id)
    assert world.chosen_id == organism.organism_id
    assert organism.protected

