from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import colorsys
import numpy as np

from eden.simulation.genome import Genome


@dataclass(slots=True)
class Organism:
    organism_id: int
    lineage_id: int
    generation: int
    x: float
    y: float
    orientation: float
    age: float
    health: float
    energy: float
    hydration: float
    genome: Genome
    parent_id: int | None
    birth_tick: int
    reproduction_cooldown: float = 0.0
    memory: np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=np.float32))
    children_count: int = 0
    current_action: str = "awakening"
    protected: bool = False
    chosen_descendant: bool = False
    death_tick: int | None = None
    death_cause: str | None = None

    @property
    def alive(self) -> bool:
        return self.death_tick is None

    @property
    def short_name(self) -> str:
        syllables = ("Ae", "Bel", "Cor", "Dae", "En", "Fira", "Glo", "Hes", "Iri", "Jun", "Kai", "Lum")
        return f"{syllables[self.organism_id % len(syllables)]}-{self.organism_id:04d}"

    @property
    def color(self) -> tuple[int, int, int]:
        red, green, blue = colorsys.hsv_to_rgb(self.genome.traits["hue"] % 1.0, 0.58, 0.96)
        return int(red * 255), int(green * 255), int(blue * 255)

    def to_dict(self) -> dict[str, Any]:
        return {
            "organism_id": self.organism_id,
            "lineage_id": self.lineage_id,
            "generation": self.generation,
            "x": self.x,
            "y": self.y,
            "orientation": self.orientation,
            "age": self.age,
            "health": self.health,
            "energy": self.energy,
            "hydration": self.hydration,
            "genome": self.genome.to_dict(),
            "parent_id": self.parent_id,
            "birth_tick": self.birth_tick,
            "reproduction_cooldown": self.reproduction_cooldown,
            "memory": self.memory.tolist(),
            "children_count": self.children_count,
            "current_action": self.current_action,
            "protected": self.protected,
            "chosen_descendant": self.chosen_descendant,
            "death_tick": self.death_tick,
            "death_cause": self.death_cause,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Organism":
        return cls(
            organism_id=int(data["organism_id"]),
            lineage_id=int(data["lineage_id"]),
            generation=int(data["generation"]),
            x=float(data["x"]),
            y=float(data["y"]),
            orientation=float(data["orientation"]),
            age=float(data["age"]),
            health=float(data["health"]),
            energy=float(data["energy"]),
            hydration=float(data["hydration"]),
            genome=Genome.from_dict(data["genome"]),
            parent_id=data.get("parent_id"),
            birth_tick=int(data["birth_tick"]),
            reproduction_cooldown=float(data.get("reproduction_cooldown", 0.0)),
            memory=np.asarray(data.get("memory", [0.0, 0.0]), dtype=np.float32),
            children_count=int(data.get("children_count", 0)),
            current_action=str(data.get("current_action", "rest")),
            protected=bool(data.get("protected", False)),
            chosen_descendant=bool(data.get("chosen_descendant", False)),
            death_tick=data.get("death_tick"),
            death_cause=data.get("death_cause"),
        )


@dataclass(slots=True)
class Lineage:
    lineage_id: int
    name: str
    founder_id: int
    emerged_tick: int
    baseline: Genome
    extinct_tick: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "lineage_id": self.lineage_id,
            "name": self.name,
            "founder_id": self.founder_id,
            "emerged_tick": self.emerged_tick,
            "baseline": self.baseline.to_dict(),
            "extinct_tick": self.extinct_tick,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Lineage":
        return cls(
            lineage_id=int(data["lineage_id"]),
            name=str(data["name"]),
            founder_id=int(data["founder_id"]),
            emerged_tick=int(data["emerged_tick"]),
            baseline=Genome.from_dict(data["baseline"]),
            extinct_tick=data.get("extinct_tick"),
        )

