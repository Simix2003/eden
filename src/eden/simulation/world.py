from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from typing import Any, Callable
import numpy as np

from eden.config import Settings
from eden.constants import ACTION_NAMES, Terrain, Weather, SEASONS
from eden.simulation.brain import decide
from eden.simulation.environment import generate_environment, update_environment
from eden.simulation.events import EventLog
from eden.simulation.evolution import assign_lineage, detect_extinctions
from eden.simulation.genome import Genome
from eden.simulation.metrics import bounded_append, snapshot_metrics
from eden.simulation.organisms import Lineage, Organism
from eden.utilities.random_utils import make_rng, restore_rng, rng_state


ARRAY_NAMES = (
    "terrain",
    "elevation",
    "water",
    "moisture",
    "fertility",
    "temperature",
    "sunlight",
    "plants",
    "signal",
    "fire",
    "ash",
)


class World:
    """Headless deterministic ecosystem state and fixed-step rules."""

    def __init__(self, settings: Settings, seed: int | None = None, populate: bool = True) -> None:
        self.settings = settings
        self.seed = int(settings.world.seed if seed is None else seed)
        self.rng = make_rng(self.seed)
        self.tick = 0
        self.simulated_seconds = 0.0
        self.weather = Weather.CLEAR
        self.weather_ticks_remaining = settings.simulation.weather_min_ticks
        self.temperature_modifier = 0.0
        self.temperature_modifier_ticks = 0
        self.organisms: dict[int, Organism] = {}
        self.lineages: dict[int, Lineage] = {}
        self.next_organism_id = 1
        self.next_lineage_id = 1
        self.total_births = 0
        self.total_deaths = 0
        self.oldest_age_record = 0.0
        self.longest_lived = 0.0
        self.chosen_id: int | None = None
        self.events = EventLog(settings.simulation.event_limit)
        self.metrics: list[dict[str, Any]] = []
        self.interventions: list[dict[str, Any]] = []
        self.death_records: list[dict[str, Any]] = []
        self.population_peak = 0
        self._lineage_centroids: dict[int, tuple[float, float]] = {}
        self.last_saved_at: float | None = None
        self.save_status = "new world"
        self._install_arrays(generate_environment(settings, self.rng))
        if populate:
            self._seed_population(settings.world.initial_population)
        self.population_peak = len(self.organisms)
        self.events.add(
            0,
            "world",
            "info",
            "EDEN awakens",
            f"A new world formed from seed {self.seed} with {len(self.organisms)} organisms.",
            key="world-awakens",
            data={"seed": self.seed, "population": len(self.organisms)},
        )

    @property
    def shape(self) -> tuple[int, int]:
        return self.terrain.shape

    @property
    def season(self) -> str:
        index = (self.tick // self.settings.simulation.season_length_ticks) % len(SEASONS)
        return SEASONS[index]

    @property
    def age_days(self) -> float:
        return self.tick / self.settings.simulation.ticks_per_day

    def _install_arrays(self, arrays: dict[str, np.ndarray]) -> None:
        expected_shape = (self.settings.world.height, self.settings.world.width)
        for name in ARRAY_NAMES:
            array = np.asarray(arrays[name])
            if array.shape != expected_shape:
                raise ValueError(f"{name} grid has shape {array.shape}, expected {expected_shape}")
            setattr(self, name, array.copy())

    def _seed_population(self, count: int) -> None:
        lineage_count = min(5, max(2, count // 25))
        founders: list[tuple[int, Genome]] = []
        for index in range(lineage_count):
            genome = Genome.random(self.rng, hue=(0.08 + index / lineage_count) % 1.0)
            location = self.find_spawn_location()
            if location is None:
                break
            organism_id = self.next_organism_id
            lineage_id = self.next_lineage_id
            self.next_lineage_id += 1
            self.lineages[lineage_id] = Lineage(
                lineage_id=lineage_id,
                name=f"Lineage {lineage_id:03d}",
                founder_id=organism_id,
                emerged_tick=0,
                baseline=genome,
            )
            self._create_organism(location[0], location[1], genome, lineage_id, None, 0, count_birth=False)
            founders.append((lineage_id, genome))
        while len(self.organisms) < count and founders:
            lineage_id, baseline = founders[len(self.organisms) % len(founders)]
            genome = baseline.mutated(self.rng, 0.22, 0.045)
            location = self.find_spawn_location()
            if location is None:
                break
            self._create_organism(location[0], location[1], genome, lineage_id, None, 0, count_birth=False)

    def find_spawn_location(self, near: tuple[float, float] | None = None) -> tuple[float, float] | None:
        height, width = self.shape
        for _ in range(80):
            if near is None:
                x = float(self.rng.uniform(1, width - 1))
                y = float(self.rng.uniform(1, height - 1))
            else:
                x = float(np.clip(near[0] + self.rng.normal(0.0, 1.2), 1, width - 2))
                y = float(np.clip(near[1] + self.rng.normal(0.0, 1.2), 1, height - 2))
            ix, iy = int(x), int(y)
            if self.terrain[iy, ix] in (Terrain.FERTILE, Terrain.DRY) and self.fire[iy, ix] < 0.1:
                if all((item.x - x) ** 2 + (item.y - y) ** 2 > 0.18 for item in self.organisms.values()):
                    return x, y
        return None

    def spawn_organism(self, x: float | None = None, y: float | None = None) -> Organism | None:
        if len(self.organisms) >= self.settings.world.maximum_population:
            return None
        location = self.find_spawn_location((x, y)) if x is not None and y is not None else self.find_spawn_location()
        if location is None:
            return None
        genome = Genome.random(self.rng)
        organism_id = self.next_organism_id
        lineage_id = self.next_lineage_id
        self.next_lineage_id += 1
        self.lineages[lineage_id] = Lineage(
            lineage_id=lineage_id,
            name=f"Lineage {lineage_id:03d}",
            founder_id=organism_id,
            emerged_tick=self.tick,
            baseline=genome,
        )
        organism = self._create_organism(*location, genome, lineage_id, None, 0, count_birth=True)
        self.events.add(
            self.tick,
            "intervention",
            "info",
            "Life was called forth",
            f"{organism.short_name} appeared as founder of Lineage {lineage_id:03d}.",
            entity_ids=[organism.organism_id],
            lineage_ids=[lineage_id],
        )
        return organism

    def _create_organism(
        self,
        x: float,
        y: float,
        genome: Genome,
        lineage_id: int,
        parent_id: int | None,
        generation: int,
        *,
        count_birth: bool,
    ) -> Organism:
        organism_id = self.next_organism_id
        self.next_organism_id += 1
        maximum = genome.traits["max_energy"]
        organism = Organism(
            organism_id=organism_id,
            lineage_id=lineage_id,
            generation=generation,
            x=x,
            y=y,
            orientation=float(self.rng.uniform(-math.pi, math.pi)),
            age=0.0,
            health=100.0,
            energy=maximum * float(self.rng.uniform(0.68, 0.88)),
            hydration=float(self.rng.uniform(70.0, 100.0)),
            genome=genome,
            parent_id=parent_id,
            birth_tick=self.tick,
            chosen_descendant=bool(parent_id is not None and self._is_chosen_line(parent_id)),
        )
        self.organisms[organism_id] = organism
        if count_birth:
            self.total_births += 1
        return organism

    def step(self, dt: float | None = None) -> None:
        delta = 1.0 / self.settings.simulation.tick_rate if dt is None else float(dt)
        if not 0.0 < delta <= 30.0:
            raise ValueError("simulation step must be in (0, 30] seconds")
        self.tick += 1
        self.simulated_seconds += delta
        self._update_weather()
        if self.temperature_modifier_ticks > 0:
            self.temperature_modifier_ticks -= 1
            if self.temperature_modifier_ticks == 0:
                self.temperature_modifier = 0.0
        update_environment(self, delta)
        self._update_organisms(delta)
        if self.tick % 20 == 0:
            self._detect_events()
        if self.tick % max(10, self.settings.simulation.tick_rate * 5) == 0:
            bounded_append(self.metrics, snapshot_metrics(self), self.settings.simulation.metric_limit)
        self._validate_fast()

    def run(self, steps: int, progress: Callable[[int, int], None] | None = None, dt: float | None = None) -> None:
        for index in range(steps):
            self.step(dt)
            if progress and (index % 50 == 0 or index + 1 == steps):
                progress(index + 1, steps)

    def _update_weather(self) -> None:
        self.weather_ticks_remaining -= 1
        if self.weather_ticks_remaining > 0:
            return
        choices = np.array(list(Weather), dtype=object)
        weights = np.asarray(self.settings.simulation.weather_weights, dtype=np.float64).copy()
        if self.season == "summer":
            weights += np.array([0.05, -0.02, -0.04, 0.02, 0.03, -0.04])
        elif self.season == "winter":
            weights += np.array([-0.03, 0.03, 0.02, -0.02, -0.04, 0.04])
        weights = np.clip(weights, 0.01, None)
        weights /= weights.sum()
        self.weather = self.rng.choice(choices, p=weights)
        low = self.settings.simulation.weather_min_ticks
        high = self.settings.simulation.weather_max_ticks
        self.weather_ticks_remaining = int(self.rng.integers(low, high + 1))
        if self.weather in (Weather.DROUGHT, Weather.HEATWAVE, Weather.COLD):
            self.events.add(
                self.tick,
                "weather",
                "warning",
                f"{self.weather.value.title()} begins",
                f"A {self.weather.value} is reshaping conditions across EDEN.",
                key=f"weather:{self.weather.value}",
                cooldown=low * 2,
            )

    def _update_organisms(self, dt: float) -> None:
        if not self.organisms:
            return
        height, width = self.shape
        occupancy = np.zeros(self.shape, dtype=np.uint16)
        for organism in self.organisms.values():
            occupancy[min(height - 1, int(organism.y)), min(width - 1, int(organism.x))] += 1
        newborns: list[tuple[Organism, Genome, tuple[float, float]]] = []
        deaths: list[tuple[int, str]] = []
        for organism_id in sorted(self.organisms):
            organism = self.organisms[organism_id]
            action, outputs = self._choose_action(organism, occupancy)
            organism.current_action = ACTION_NAMES[action]
            self._apply_action(organism, action, dt, newborns)
            cause = self._apply_vital_costs(organism, dt)
            organism.memory[:] = np.tanh([outputs[action], organism.energy / max(1.0, organism.genome.traits["max_energy"])])
            if cause is not None:
                deaths.append((organism_id, cause))
        for parent, genome, location in newborns:
            if len(self.organisms) >= self.settings.world.maximum_population:
                break
            child_id = self.next_organism_id
            lineage_id = assign_lineage(self, parent, genome, child_id)
            child = self._create_organism(
                location[0], location[1], genome, lineage_id, parent.organism_id, parent.generation + 1, count_birth=True
            )
            parent.children_count += 1
            if self.total_births == 1:
                self.events.add(
                    self.tick,
                    "life",
                    "major",
                    "The first child",
                    f"{child.short_name} was born to {parent.short_name}.",
                    key="first-birth",
                    entity_ids=[child.organism_id, parent.organism_id],
                    lineage_ids=[child.lineage_id],
                )
            if child.chosen_descendant:
                self.events.add(
                    self.tick,
                    "chosen",
                    "info",
                    "The marked line continues",
                    f"{child.short_name} carries the legacy of The Chosen.",
                    key=f"chosen-descendant:{child.organism_id}",
                    entity_ids=[child.organism_id, parent.organism_id],
                )
            if parent.protected:
                self.events.add(
                    self.tick,
                    "life",
                    "info",
                    "A blessed line grows",
                    f"Protected {parent.short_name} produced descendant {child.short_name}.",
                    key=f"protected-descendant:{parent.organism_id}:{parent.children_count}",
                    entity_ids=[child.organism_id, parent.organism_id],
                    lineage_ids=[child.lineage_id],
                )
        for organism_id, cause in deaths:
            self._record_death(organism_id, cause)

    def _choose_action(self, organism: Organism, occupancy: np.ndarray) -> tuple[int, np.ndarray]:
        height, width = self.shape
        ix, iy = int(organism.x), int(organism.y)
        ahead_x = int(np.clip(organism.x + math.cos(organism.orientation), 0, width - 1))
        ahead_y = int(np.clip(organism.y + math.sin(organism.orientation), 0, height - 1))
        temp_comfort = 1.0 - min(1.0, abs(float(self.temperature[iy, ix]) - organism.genome.traits["preferred_temperature"]) / 24.0)
        water_near = float(self.water[max(0, iy - 1) : min(height, iy + 2), max(0, ix - 1) : min(width, ix + 2)].max())
        obstacle = float(self.terrain[ahead_y, ahead_x] in (Terrain.WATER, Terrain.ROCK))
        sensors = np.asarray(
            [
                organism.energy / organism.genome.traits["max_energy"],
                organism.hydration / 100.0,
                organism.age / organism.genome.traits["lifespan"],
                organism.health / 100.0,
                temp_comfort,
                self.plants[iy, ix],
                self.plants[ahead_y, ahead_x],
                self.water[iy, ix],
                water_near,
                obstacle,
                min(1.0, occupancy[iy, ix] / 5.0),
                self.signal[iy, ix],
                organism.memory[0],
                organism.memory[1],
                math.sin(organism.orientation),
                float(self.rng.uniform(-1.0, 1.0)),
            ],
            dtype=np.float32,
        )
        bias = np.zeros(len(ACTION_NAMES), dtype=np.float32)
        if organism.energy < organism.genome.traits["max_energy"] * 0.72 and self.plants[iy, ix] > 0.025:
            bias[3] += 2.2
        if organism.hydration < 68.0 and water_near > 0.04:
            bias[4] += 2.35
        if obstacle:
            bias[1 if self.rng.random() < 0.5 else 2] += 2.0
            bias[0] -= 1.5
        evo = self.settings.evolution
        crowding = len(self.organisms) / self.settings.world.maximum_population
        reproduction_ratio = min(0.90, evo.reproduction_energy_ratio + 0.20 * crowding * crowding)
        if (
            organism.energy > organism.genome.traits["max_energy"] * reproduction_ratio
            and organism.age >= evo.minimum_reproduction_age_seconds
            and organism.reproduction_cooldown <= 0.0
            and len(self.organisms) < self.settings.world.maximum_population
        ):
            bias[6] += 1.75
        if organism.energy < organism.genome.traits["max_energy"] * 0.2:
            bias[5] += 0.8
        return decide(organism.genome, sensors, bias)

    def _apply_action(
        self,
        organism: Organism,
        action: int,
        dt: float,
        newborns: list[tuple[Organism, Genome, tuple[float, float]]],
    ) -> None:
        height, width = self.shape
        ix, iy = int(organism.x), int(organism.y)
        traits = organism.genome.traits
        if action == 0:
            distance = traits["speed"] * dt
            nx = float(np.clip(organism.x + math.cos(organism.orientation) * distance, 0.01, width - 1.01))
            ny = float(np.clip(organism.y + math.sin(organism.orientation) * distance, 0.01, height - 1.01))
            if self.terrain[int(ny), int(nx)] not in (Terrain.WATER, Terrain.ROCK):
                organism.x, organism.y = nx, ny
                organism.energy -= 0.16 * traits["size"] * distance
            else:
                organism.orientation += 0.8
        elif action == 1:
            organism.orientation = (organism.orientation - 1.55 * dt) % (2 * math.pi)
        elif action == 2:
            organism.orientation = (organism.orientation + 1.55 * dt) % (2 * math.pi)
        elif action == 3:
            available = float(self.plants[iy, ix])
            amount = min(available, 0.18 * traits["food_efficiency"] * dt)
            if amount > 0.0:
                self.plants[iy, ix] -= amount
                organism.energy = min(traits["max_energy"], organism.energy + amount * 24.0)
        elif action == 4:
            y0, y1 = max(0, iy - 1), min(height, iy + 2)
            x0, x1 = max(0, ix - 1), min(width, ix + 2)
            region = self.water[y0:y1, x0:x1]
            if float(region.max()) > 0.015:
                local_index = np.unravel_index(int(np.argmax(region)), region.shape)
                consumed = min(float(region[local_index]), 0.002 * dt)
                region[local_index] -= consumed
                organism.hydration = min(100.0, organism.hydration + 22.0 * dt)
        elif action == 5:
            organism.energy = min(traits["max_energy"], organism.energy + 0.11 * dt)
        elif action == 6:
            evo = self.settings.evolution
            cost = traits["reproductive_cost"]
            crowding = (len(self.organisms) + len(newborns)) / self.settings.world.maximum_population
            reproduction_ratio = min(0.90, evo.reproduction_energy_ratio + 0.20 * crowding * crowding)
            if (
                organism.energy > max(cost + 4.0, traits["max_energy"] * reproduction_ratio)
                and organism.age >= evo.minimum_reproduction_age_seconds
                and organism.reproduction_cooldown <= 0.0
                and len(self.organisms) + len(newborns) < self.settings.world.maximum_population
            ):
                location = self.find_spawn_location((organism.x, organism.y))
                if location is not None:
                    genome = organism.genome.mutated(self.rng, evo.mutation_rate, evo.mutation_scale)
                    organism.energy -= cost
                    organism.reproduction_cooldown = evo.reproduction_cooldown_seconds
                    newborns.append((organism, genome, location))
        elif action == 7:
            self.signal[iy, ix] = min(1.0, self.signal[iy, ix] + 0.42)
            organism.energy -= 0.03 * dt

    def _apply_vital_costs(self, organism: Organism, dt: float) -> str | None:
        traits = organism.genome.traits
        sim = self.settings.simulation
        chosen_multiplier = 1.0
        if organism.organism_id == self.chosen_id or organism.protected:
            chosen_multiplier -= self.settings.evolution.chosen_advantage
        organism.age += dt
        organism.reproduction_cooldown = max(0.0, organism.reproduction_cooldown - dt)
        organism.energy -= sim.base_metabolism * traits["metabolism"] * traits["size"] * dt * chosen_multiplier
        organism.hydration -= (0.18 + traits["metabolism"] * 0.08) * dt * chosen_multiplier
        ix, iy = int(organism.x), int(organism.y)
        discomfort = max(0.0, abs(float(self.temperature[iy, ix]) - traits["preferred_temperature"]) - 9.0)
        if discomfort > 0:
            organism.health -= discomfort * 0.038 * dt * chosen_multiplier
        fire = float(self.fire[iy, ix])
        if fire > 0.02:
            organism.health -= fire * 24.0 * dt * chosen_multiplier
            if organism.health <= 0:
                return "fire"
        if organism.energy <= 0:
            organism.health -= 6.0 * dt * chosen_multiplier
            organism.energy = 0.0
            if organism.health <= 0:
                return "starvation"
        if organism.hydration <= 0:
            organism.health -= 9.0 * dt * chosen_multiplier
            organism.hydration = 0.0
            if organism.health <= 0:
                return "dehydration"
        if organism.age > traits["lifespan"]:
            if self.settings.evolution.chosen_immortal and organism.organism_id == self.chosen_id:
                organism.age = traits["lifespan"] * 0.96
            else:
                return "old age"
        if organism.health <= 0:
            return "temperature stress"
        organism.health = min(100.0, organism.health + 0.025 * dt)
        return None

    def _record_death(self, organism_id: int, cause: str) -> None:
        organism = self.organisms.pop(organism_id, None)
        if organism is None:
            return
        organism.death_tick = self.tick
        organism.death_cause = cause
        self.total_deaths += 1
        self.longest_lived = max(self.longest_lived, organism.age)
        self.death_records.append(
            {
                "organism_id": organism.organism_id,
                "lineage_id": organism.lineage_id,
                "generation": organism.generation,
                "age": organism.age,
                "cause": cause,
                "death_tick": self.tick,
            }
        )
        if len(self.death_records) > 300:
            del self.death_records[: len(self.death_records) - 300]
        if self.total_deaths == 1:
            self.events.add(
                self.tick,
                "life",
                "major",
                "The first natural death",
                f"{organism.short_name} died from {cause} after {organism.age:.1f} seconds.",
                key="first-death",
                entity_ids=[organism_id],
                lineage_ids=[organism.lineage_id],
                data={"age": organism.age, "cause": cause},
            )
        if organism_id == self.chosen_id:
            self.chosen_id = None
            self.events.add(
                self.tick,
                "chosen",
                "major",
                "The Chosen has fallen",
                f"{organism.short_name} died from {cause}; its marked descendants remain.",
                key=f"chosen-death:{organism_id}",
                entity_ids=[organism_id],
            )

    def _is_chosen_line(self, organism_id: int) -> bool:
        organism = self.organisms.get(organism_id)
        return bool(organism and (organism.organism_id == self.chosen_id or organism.chosen_descendant))

    def choose(self, organism_id: int) -> bool:
        organism = self.organisms.get(organism_id)
        if organism is None:
            return False
        if self.chosen_id in self.organisms:
            self.organisms[self.chosen_id].chosen_descendant = True
        self.chosen_id = organism_id
        organism.chosen_descendant = True
        self.events.add(
            self.tick,
            "chosen",
            "major",
            "One life was chosen",
            f"{organism.short_name} of Lineage {organism.lineage_id:03d} now bears the mark.",
            key=f"chosen:{organism_id}",
            entity_ids=[organism_id],
            lineage_ids=[organism.lineage_id],
        )
        return True

    def bless(self, organism_id: int, enabled: bool = True) -> bool:
        organism = self.organisms.get(organism_id)
        if organism is None:
            return False
        organism.protected = enabled
        self.events.add(
            self.tick,
            "intervention",
            "info",
            "A blessing was bestowed" if enabled else "A blessing was lifted",
            f"{organism.short_name} is {'protected' if enabled else 'returned fully to natural law'}.",
            key=f"bless:{organism_id}:{enabled}",
            entity_ids=[organism_id],
        )
        return True

    def mutate_organism(self, organism_id: int) -> bool:
        organism = self.organisms.get(organism_id)
        if organism is None:
            return False
        organism.genome = organism.genome.mutated(self.rng, 0.62, self.settings.evolution.mutation_scale * 1.7)
        self.events.add(
            self.tick,
            "intervention",
            "warning",
            "A genome was rewritten",
            f"{organism.short_name} received a directed burst of mutation.",
            key=f"mutate:{organism_id}:{self.tick}",
            entity_ids=[organism_id],
        )
        return True

    def apply_intervention(self, kind: str, x: float, y: float, radius: float | None = None) -> bool:
        valid = {"rain", "drought", "plants", "fire", "extinguish", "water", "spawn", "smite", "heat", "cold"}
        if kind not in valid:
            raise ValueError(f"unknown intervention: {kind}")
        config = self.settings.interventions
        radius_value = float(config.radius if radius is None else radius)
        height, width = self.shape
        cx, cy = float(np.clip(x, 0, width - 1)), float(np.clip(y, 0, height - 1))
        yy, xx = np.ogrid[:height, :width]
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius_value**2
        affected = int(mask.sum())
        if kind == "rain":
            self.moisture[mask] = np.clip(self.moisture[mask] + config.rain_strength, 0.0, 1.0)
            self.water[mask & (self.terrain == Terrain.WATER)] = np.clip(
                self.water[mask & (self.terrain == Terrain.WATER)] + config.rain_strength * 0.35, 0.0, 1.0
            )
        elif kind == "drought":
            self.moisture[mask] = np.clip(self.moisture[mask] - config.drought_strength, 0.0, 1.0)
            self.water[mask] = np.clip(self.water[mask] - config.drought_strength * 0.35, 0.0, 1.0)
        elif kind == "plants":
            soil = mask & (self.terrain != Terrain.WATER) & (self.terrain != Terrain.ROCK)
            self.plants[soil] = np.clip(self.plants[soil] + config.plant_strength, 0.0, 1.0)
            self.fertility[soil] = np.clip(self.fertility[soil] + config.plant_strength * 0.3, 0.0, 1.0)
        elif kind == "fire":
            fuel = mask & (self.plants > 0.04) & (self.terrain != Terrain.WATER)
            self.fire[fuel] = np.maximum(self.fire[fuel], config.fire_strength)
        elif kind == "extinguish":
            self.fire[mask] = 0.0
            self.moisture[mask] = np.clip(self.moisture[mask] + 0.18, 0.0, 1.0)
        elif kind == "water":
            convertible = mask & (self.terrain != Terrain.ROCK)
            self.terrain[convertible] = Terrain.WATER
            self.water[convertible] = np.maximum(self.water[convertible], 0.62)
            self.moisture[convertible] = 1.0
            self.plants[convertible] = 0.0
            for organism in self.organisms.values():
                if convertible[int(organism.y), int(organism.x)]:
                    location = self.find_spawn_location((organism.x, organism.y))
                    if location is not None:
                        organism.x, organism.y = location
        elif kind == "spawn":
            if self.spawn_organism(cx, cy) is None:
                return False
        elif kind == "smite":
            self.plants[mask] *= 0.18
            for organism in self.organisms.values():
                if (organism.x - cx) ** 2 + (organism.y - cy) ** 2 <= radius_value**2:
                    organism.health = max(1.0, organism.health - 58.0)
        elif kind in ("heat", "cold"):
            self.temperature_modifier = config.temperature_delta * (1.0 if kind == "heat" else -1.0)
            self.temperature_modifier_ticks = self.settings.simulation.tick_rate * 60
        record = {"tick": self.tick, "kind": kind, "x": cx, "y": cy, "radius": radius_value, "affected": affected}
        self.interventions.append(record)
        if len(self.interventions) > 200:
            del self.interventions[: len(self.interventions) - 200]
        self.events.add(
            self.tick,
            "intervention",
            "warning" if kind in ("fire", "drought", "smite") else "info",
            f"Divine {kind}",
            f"The {kind} intervention touched {affected} cells near ({cx:.0f}, {cy:.0f}).",
            key=f"intervention:{kind}:{self.tick}",
            data={"x": cx, "y": cy, "radius": radius_value, "affected_cells": affected},
        )
        return True

    def _detect_events(self) -> None:
        population = len(self.organisms)
        self.population_peak = max(self.population_peak, population)
        if population >= 50 and population % 50 < 3:
            milestone = max(50, (population // 50) * 50)
            self.events.add(
                self.tick,
                "population",
                "info",
                f"Population crossed {milestone}",
                f"EDEN now supports {population} living organisms.",
                key=f"population:{milestone}",
                cooldown=1000,
                data={"population": population},
            )
        if self.population_peak >= 30 and population < self.population_peak * 0.55:
            self.events.add(
                self.tick,
                "population",
                "major",
                "Population crash",
                f"The population fell from a peak of {self.population_peak} to {population}.",
                key="population-crash",
                cooldown=self.settings.simulation.season_length_ticks,
                data={"peak": self.population_peak, "population": population},
            )
        burning = int((self.fire > 0.05).sum())
        if burning > 35:
            self.events.add(
                self.tick,
                "disaster",
                "major",
                "Major fire",
                f"Flame is active across {burning} cells.",
                key="major-fire",
                cooldown=900,
                data={"burning_cells": burning},
            )
        if self.weather == Weather.DROUGHT and float(self.moisture.mean()) < 0.22:
            self.events.add(
                self.tick,
                "disaster",
                "major",
                "Severe drought",
                f"Mean world moisture fell to {self.moisture.mean():.2f}.",
                key="severe-drought",
                cooldown=1200,
                data={"mean_moisture": float(self.moisture.mean())},
            )
            survivor = max(self.organisms.values(), key=lambda item: item.age, default=None)
            if survivor is not None and survivor.age > 120.0 and survivor.hydration > 55.0:
                self.events.add(
                    self.tick,
                    "record",
                    "info",
                    "Unusual survival",
                    f"{survivor.short_name} remains hydrated after {survivor.age:.0f} seconds through severe drought.",
                    key=f"drought-survivor:{survivor.organism_id}",
                    cooldown=1600,
                    entity_ids=[survivor.organism_id],
                    lineage_ids=[survivor.lineage_id],
                    data={"age": survivor.age, "hydration": survivor.hydration},
                )
        if burning == 0 and any(event.title == "Major fire" for event in self.events.events[-20:]) and float(self.plants.mean()) > 0.10:
            self.events.add(
                self.tick,
                "recovery",
                "info",
                "Green returns",
                "The last major burn area is quiet and plant cover is recovering.",
                key="fire-recovery",
                cooldown=1600,
                data={"plant_cover": float(self.plants.mean())},
            )
        counts = Counter(item.lineage_id for item in self.organisms.values())
        if counts and population >= 20:
            dominant, count = counts.most_common(1)[0]
            if count / population >= 0.68:
                self.events.add(
                    self.tick,
                    "evolution",
                    "warning",
                    "A lineage dominates",
                    f"Lineage {dominant:03d} now represents {count / population:.0%} of life.",
                    key=f"dominance:{dominant}",
                    cooldown=1500,
                    lineage_ids=[dominant],
                    data={"share": count / population},
                )
        for lineage_id in counts:
            members = [item for item in self.organisms.values() if item.lineage_id == lineage_id]
            centroid = (sum(item.x for item in members) / len(members), sum(item.y for item in members) / len(members))
            previous = self._lineage_centroids.get(lineage_id)
            if previous and len(members) >= 6:
                distance = math.dist(previous, centroid)
                if distance > min(self.shape) * 0.22:
                    self.events.add(
                        self.tick,
                        "migration",
                        "info",
                        "A lineage migrated",
                        f"Lineage {lineage_id:03d} shifted its center by {distance:.1f} cells.",
                        key=f"migration:{lineage_id}",
                        cooldown=1800,
                        lineage_ids=[lineage_id],
                        data={"distance": distance},
                    )
            self._lineage_centroids[lineage_id] = centroid
        detect_extinctions(self)
        for organism in self.organisms.values():
            if organism.age > self.oldest_age_record + 30.0:
                self.oldest_age_record = organism.age
                self.events.add(
                    self.tick,
                    "record",
                    "info",
                    "A new age record",
                    f"{organism.short_name} has survived for {organism.age:.0f} seconds.",
                    key=f"age-record:{int(organism.age // 60)}",
                    cooldown=200,
                    entity_ids=[organism.organism_id],
                    data={"age": organism.age},
                )

    def _validate_fast(self) -> None:
        if len(self.organisms) > self.settings.world.maximum_population:
            raise RuntimeError("population cap violated")
        for organism in self.organisms.values():
            if not (0.0 <= organism.x < self.shape[1] and 0.0 <= organism.y < self.shape[0]):
                raise RuntimeError("organism moved outside the world")
            if not all(math.isfinite(value) for value in (organism.energy, organism.hydration, organism.health, organism.age)):
                raise RuntimeError("non-finite organism state")

    def validate_full(self) -> None:
        self._validate_fast()
        for name in ARRAY_NAMES:
            array = getattr(self, name)
            if not bool(np.isfinite(array).all()):
                raise RuntimeError(f"non-finite values in {name}")
        if int(self.terrain.min()) < int(Terrain.WATER) or int(self.terrain.max()) > int(Terrain.ROCK):
            raise RuntimeError("invalid terrain value")
        for name in ("water", "moisture", "fertility", "sunlight", "plants", "signal", "fire", "ash"):
            array = getattr(self, name)
            if float(array.min()) < -1e-6 or float(array.max()) > 1.000001:
                raise RuntimeError(f"{name} escaped [0, 1]")

    def metadata(self, include_clock: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": 1,
            "seed": self.seed,
            "tick": self.tick,
            "simulated_seconds": self.simulated_seconds,
            "weather": self.weather.value,
            "weather_ticks_remaining": self.weather_ticks_remaining,
            "temperature_modifier": self.temperature_modifier,
            "temperature_modifier_ticks": self.temperature_modifier_ticks,
            "next_organism_id": self.next_organism_id,
            "next_lineage_id": self.next_lineage_id,
            "total_births": self.total_births,
            "total_deaths": self.total_deaths,
            "oldest_age_record": self.oldest_age_record,
            "longest_lived": self.longest_lived,
            "chosen_id": self.chosen_id,
            "population_peak": self.population_peak,
            "organisms": [self.organisms[key].to_dict() for key in sorted(self.organisms)],
            "lineages": [self.lineages[key].to_dict() for key in sorted(self.lineages)],
            "events": self.events.to_dict(),
            "metrics": self.metrics,
            "interventions": self.interventions,
            "death_records": self.death_records,
            "lineage_centroids": {str(key): list(value) for key, value in self._lineage_centroids.items()},
            "rng_state": rng_state(self.rng),
            "settings": {
                "world": asdict(self.settings.world),
                "simulation": asdict(self.settings.simulation),
                "evolution": asdict(self.settings.evolution),
                "persistence": asdict(self.settings.persistence),
                "ui": asdict(self.settings.ui),
                "interventions": asdict(self.settings.interventions),
            },
        }
        if include_clock:
            data["last_saved_at"] = self.last_saved_at
        return data

    @classmethod
    def from_snapshot(cls, settings: Settings, metadata: dict[str, Any], arrays: dict[str, np.ndarray]) -> "World":
        if int(metadata.get("schema_version", 0)) != 1:
            raise ValueError("unsupported world snapshot version")
        world = cls.__new__(cls)
        world.settings = settings
        world.seed = int(metadata["seed"])
        world.rng = restore_rng(metadata["rng_state"])
        world.tick = int(metadata["tick"])
        world.simulated_seconds = float(metadata["simulated_seconds"])
        world.weather = Weather(metadata["weather"])
        world.weather_ticks_remaining = int(metadata["weather_ticks_remaining"])
        world.temperature_modifier = float(metadata.get("temperature_modifier", 0.0))
        world.temperature_modifier_ticks = int(metadata.get("temperature_modifier_ticks", 0))
        world.next_organism_id = int(metadata["next_organism_id"])
        world.next_lineage_id = int(metadata["next_lineage_id"])
        world.total_births = int(metadata["total_births"])
        world.total_deaths = int(metadata["total_deaths"])
        world.oldest_age_record = float(metadata.get("oldest_age_record", 0.0))
        world.longest_lived = float(metadata.get("longest_lived", 0.0))
        world.chosen_id = metadata.get("chosen_id")
        world.population_peak = int(metadata.get("population_peak", 0))
        world.organisms = {int(item["organism_id"]): Organism.from_dict(item) for item in metadata["organisms"]}
        world.lineages = {int(item["lineage_id"]): Lineage.from_dict(item) for item in metadata["lineages"]}
        world.events = EventLog.from_dict(metadata["events"])
        world.metrics = list(metadata.get("metrics", []))[-settings.simulation.metric_limit :]
        world.interventions = list(metadata.get("interventions", []))[-200:]
        world.death_records = list(metadata.get("death_records", []))[-300:]
        world._lineage_centroids = {
            int(key): (float(value[0]), float(value[1])) for key, value in metadata.get("lineage_centroids", {}).items()
        }
        world.last_saved_at = metadata.get("last_saved_at")
        world.save_status = "restored"
        world._install_arrays(arrays)
        world.validate_full()
        return world

    def state_hash(self) -> str:
        digest = hashlib.sha256()
        metadata = self.metadata(include_clock=False)
        digest.update(json.dumps(metadata, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))
        for name in ARRAY_NAMES:
            array = np.ascontiguousarray(getattr(self, name))
            digest.update(name.encode("ascii"))
            digest.update(array.dtype.str.encode("ascii"))
            digest.update(array.tobytes())
        return digest.hexdigest()
