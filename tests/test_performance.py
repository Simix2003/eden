from __future__ import annotations

from eden.simulation.world import World
from eden.utilities.profiling import benchmark_world


def test_representative_core_performance(settings) -> None:
    world = World(settings, seed=24)
    result = benchmark_world(world, 250)
    assert result.ticks_per_second > 20
    assert result.population <= settings.world.maximum_population

