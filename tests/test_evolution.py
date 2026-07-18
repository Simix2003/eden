from __future__ import annotations

from eden.simulation.evolution import assign_lineage, detect_extinctions
from eden.simulation.genome import TRAIT_BOUNDS
from eden.simulation.world import World


def test_child_genome_resembles_parent_and_is_bounded(settings) -> None:
    world = World(settings, seed=14)
    parent = next(iter(world.organisms.values()))
    child = parent.genome.mutated(world.rng, 0.1, 0.05)
    assert child.distance(parent.genome) < 0.2
    for key, value in child.traits.items():
        low, high = TRAIT_BOUNDS[key]
        assert low <= value <= high
    assert float(abs(child.weights_1).max()) <= 3.0
    assert float(abs(child.weights_2).max()) <= 3.0


def test_lineage_can_diverge(settings) -> None:
    settings.evolution.species_divergence_threshold = 0.0
    world = World(settings, seed=15)
    parent = next(iter(world.organisms.values()))
    genome = parent.genome.mutated(world.rng, 1.0, 0.2)
    lineage_id = assign_lineage(world, parent, genome, world.next_organism_id)
    assert lineage_id != parent.lineage_id
    assert lineage_id in world.lineages


def test_species_extinction_is_detected(settings) -> None:
    world = World(settings, seed=16)
    target = next(iter(world.lineages))
    for organism_id in [item.organism_id for item in world.organisms.values() if item.lineage_id == target]:
        world._record_death(organism_id, "test")
    world.tick += 1
    detect_extinctions(world)
    assert world.lineages[target].extinct_tick == world.tick
    assert any(event.title == "A lineage fell silent" for event in world.events.events)

