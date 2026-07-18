from __future__ import annotations

from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eden.config import Settings


@pytest.fixture
def settings() -> Settings:
    value = Settings()
    value.world.width = 48
    value.world.height = 48
    value.world.initial_population = 24
    value.world.maximum_population = 80
    value.simulation.tick_rate = 8
    value.simulation.ticks_per_day = 160
    value.simulation.season_length_ticks = 800
    value.simulation.weather_min_ticks = 120
    value.simulation.weather_max_ticks = 220
    value.simulation.event_limit = 80
    value.simulation.metric_limit = 60
    value.evolution.minimum_reproduction_age_seconds = 4.0
    value.evolution.reproduction_cooldown_seconds = 6.0
    value.persistence.save_interval_seconds = 10
    value.persistence.retained_snapshots = 3
    value.persistence.offline_catchup_cap_seconds = 60
    value.persistence.offline_catchup_max_steps = 120
    value.validate()
    return value

