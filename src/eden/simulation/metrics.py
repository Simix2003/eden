from __future__ import annotations

from collections import Counter
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from eden.simulation.world import World


def snapshot_metrics(world: "World") -> dict[str, Any]:
    populations = Counter(organism.lineage_id for organism in world.organisms.values())
    dominant = max(populations, key=populations.get) if populations else 0
    mean_energy = sum(item.energy for item in world.organisms.values()) / max(1, len(world.organisms))
    trait_names = ("speed", "size", "metabolism", "preferred_temperature", "food_efficiency")
    averages = {
        name: sum(item.genome.traits[name] for item in world.organisms.values()) / max(1, len(world.organisms))
        for name in trait_names
    }
    return {
        "tick": world.tick,
        "population": len(world.organisms),
        "species": len(populations),
        "births": world.total_births,
        "deaths": world.total_deaths,
        "dominant_lineage": dominant,
        "plant_cover": float(world.plants.mean()),
        "mean_energy": float(mean_energy),
        "burning_cells": int((world.fire > 0.05).sum()),
        "weather": world.weather.value,
        "lineage_populations": {str(key): value for key, value in sorted(populations.items())},
        "average_traits": averages,
    }


def bounded_append(items: list[dict[str, Any]], item: dict[str, Any], limit: int) -> None:
    items.append(item)
    if len(items) > limit:
        del items[: len(items) - limit]
