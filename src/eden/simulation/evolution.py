from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from eden.simulation.organisms import Lineage

if TYPE_CHECKING:
    from eden.simulation.organisms import Genome, Organism
    from eden.simulation.world import World


def assign_lineage(world: "World", parent: "Organism", child_genome: "Genome", child_id: int) -> int:
    lineage = world.lineages[parent.lineage_id]
    distance = child_genome.distance(lineage.baseline)
    if distance <= world.settings.evolution.species_divergence_threshold:
        return parent.lineage_id
    lineage_id = world.next_lineage_id
    world.next_lineage_id += 1
    world.lineages[lineage_id] = Lineage(
        lineage_id=lineage_id,
        name=f"Lineage {lineage_id:03d}",
        founder_id=child_id,
        emerged_tick=world.tick,
        baseline=child_genome,
    )
    world.events.add(
        world.tick,
        "evolution",
        "major",
        "A new lineage emerged",
        f"Genetic drift produced Lineage {lineage_id:03d} at distance {distance:.3f}.",
        key=f"emergence:{lineage_id}",
        entity_ids=[child_id],
        lineage_ids=[lineage_id],
        data={"genome_distance": distance},
    )
    return lineage_id


def detect_extinctions(world: "World") -> None:
    living = Counter(item.lineage_id for item in world.organisms.values())
    for lineage_id, lineage in world.lineages.items():
        if lineage.extinct_tick is None and lineage_id not in living and world.tick > lineage.emerged_tick:
            lineage.extinct_tick = world.tick
            world.events.add(
                world.tick,
                "evolution",
                "major",
                "A lineage fell silent",
                f"{lineage.name} has no living members.",
                key=f"extinction:{lineage_id}",
                lineage_ids=[lineage_id],
            )

