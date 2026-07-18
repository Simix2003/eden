from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import tomllib


@dataclass(slots=True)
class WorldConfig:
    seed: int = 314159
    width: int = 128
    height: int = 128
    initial_population: int = 110
    maximum_population: int = 260


@dataclass(slots=True)
class SimulationConfig:
    tick_rate: int = 8
    ticks_per_day: int = 480
    season_length_ticks: int = 7200
    weather_min_ticks: int = 320
    weather_max_ticks: int = 1100
    weather_weights: list[float] = field(default_factory=lambda: [0.36, 0.20, 0.22, 0.08, 0.07, 0.07])
    plant_growth_rate: float = 0.085
    plant_spread_rate: float = 0.026
    base_metabolism: float = 0.44
    event_limit: int = 300
    metric_limit: int = 720


@dataclass(slots=True)
class EvolutionConfig:
    mutation_rate: float = 0.075
    mutation_scale: float = 0.09
    species_divergence_threshold: float = 0.18
    reproduction_energy_ratio: float = 0.68
    reproduction_cooldown_seconds: float = 60.0
    minimum_reproduction_age_seconds: float = 20.0
    chosen_advantage: float = 0.08
    chosen_immortal: bool = False


@dataclass(slots=True)
class PersistenceConfig:
    database_path: str = "data/saves/eden.db"
    save_interval_seconds: int = 30
    retained_snapshots: int = 5
    offline_catchup_cap_seconds: int = 3600
    offline_catchup_max_steps: int = 2400


@dataclass(slots=True)
class UIConfig:
    width: int = 1440
    height: int = 900
    render_fps: int = 30
    fullscreen: bool = False
    ui_scale: float = 1.0
    performance_mode: str = "balanced"
    audio_enabled: bool = False


@dataclass(slots=True)
class InterventionConfig:
    radius: int = 8
    rain_strength: float = 0.32
    drought_strength: float = 0.28
    plant_strength: float = 0.55
    fire_strength: float = 0.85
    temperature_delta: float = 8.0


@dataclass(slots=True)
class Settings:
    world: WorldConfig = field(default_factory=WorldConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    evolution: EvolutionConfig = field(default_factory=EvolutionConfig)
    persistence: PersistenceConfig = field(default_factory=PersistenceConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    interventions: InterventionConfig = field(default_factory=InterventionConfig)
    source_path: Path | None = None

    def validate(self) -> None:
        if not 32 <= self.world.width <= 512 or not 32 <= self.world.height <= 512:
            raise ValueError("world dimensions must be between 32 and 512")
        if not 1 <= self.world.initial_population <= self.world.maximum_population:
            raise ValueError("initial_population must be positive and at most maximum_population")
        if not 1 <= self.world.maximum_population <= 2000:
            raise ValueError("maximum_population must be between 1 and 2000")
        if not 1 <= self.simulation.tick_rate <= 60:
            raise ValueError("tick_rate must be between 1 and 60")
        if self.simulation.season_length_ticks < 100:
            raise ValueError("season_length_ticks is too small")
        if (
            len(self.simulation.weather_weights) != 6
            or any(value <= 0 for value in self.simulation.weather_weights)
            or self.simulation.weather_min_ticks < 10
            or self.simulation.weather_max_ticks < self.simulation.weather_min_ticks
        ):
            raise ValueError("weather requires six positive weights and a valid duration range")
        if not 0.0 <= self.evolution.mutation_rate <= 1.0:
            raise ValueError("mutation_rate must be in [0, 1]")
        if not 0.0 <= self.evolution.chosen_advantage <= 0.25:
            raise ValueError("chosen_advantage must be in [0, 0.25]")
        if self.persistence.retained_snapshots < 2:
            raise ValueError("at least two snapshots must be retained")
        if self.ui.render_fps < 5 or self.ui.render_fps > 120:
            raise ValueError("render_fps must be between 5 and 120")


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _populate(section: Any, values: dict[str, Any]) -> None:
    for key, value in values.items():
        if not hasattr(section, key):
            raise ValueError(f"unknown configuration value: {type(section).__name__}.{key}")
        setattr(section, key, value)


def load_settings(path: str | Path | None = None) -> Settings:
    config_path = Path(path) if path else project_root() / "config" / "default.toml"
    settings = Settings(source_path=config_path)
    if config_path.exists():
        with config_path.open("rb") as handle:
            raw = tomllib.load(handle)
        for name in ("world", "simulation", "evolution", "persistence", "ui", "interventions"):
            if name in raw:
                _populate(getattr(settings, name), raw[name])
    settings.validate()
    return settings


def settings_from_dict(data: dict[str, Any], source_path: Path | None = None) -> Settings:
    """Rebuild the ecological contract embedded in a validated snapshot."""
    settings = Settings(source_path=source_path)
    for name in ("world", "simulation", "evolution", "persistence", "ui", "interventions"):
        values = data.get(name)
        if not isinstance(values, dict):
            raise ValueError(f"saved settings are missing the {name} section")
        _populate(getattr(settings, name), values)
    settings.validate()
    return settings
