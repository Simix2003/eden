from __future__ import annotations

from eden.simulation.world import World


def test_long_headless_run_stays_bounded_and_finite(settings) -> None:
    world = World(settings, seed=23)
    world.run(1200)
    world.validate_full()
    assert len(world.organisms) <= settings.world.maximum_population
    assert len(world.events.events) <= settings.simulation.event_limit
    assert len(world.metrics) <= settings.simulation.metric_limit
    assert all(item.energy >= 0 and item.hydration >= 0 for item in world.organisms.values())

