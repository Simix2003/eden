from __future__ import annotations

from eden.simulation.world import World


def test_same_seed_and_ordered_interventions_match(settings) -> None:
    first = World(settings, seed=222)
    second = World(settings, seed=222)
    for world in (first, second):
        world.run(30)
        world.apply_intervention("rain", 12, 20, 5)
        world.run(40)
        organism_id = min(world.organisms)
        world.choose(organism_id)
        world.mutate_organism(organism_id)
        world.apply_intervention("plants", 30, 15, 4)
        world.run(50)
    assert first.state_hash() == second.state_hash()


def test_different_seed_changes_world(settings) -> None:
    assert World(settings, seed=1).state_hash() != World(settings, seed=2).state_hash()

