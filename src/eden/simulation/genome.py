from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np

from eden.constants import HIDDEN_COUNT, INPUT_COUNT, OUTPUT_COUNT


TRAIT_BOUNDS: dict[str, tuple[float, float]] = {
    "speed": (0.45, 2.2),
    "size": (0.55, 1.65),
    "max_energy": (65.0, 150.0),
    "lifespan": (150.0, 720.0),
    "vision": (1.0, 5.0),
    "preferred_temperature": (5.0, 32.0),
    "metabolism": (0.55, 1.55),
    "reproductive_cost": (18.0, 52.0),
    "food_efficiency": (0.6, 1.8),
    "hue": (0.0, 1.0),
    "mutation_rate": (0.02, 0.22),
}


@dataclass(slots=True)
class Genome:
    traits: dict[str, float]
    weights_1: np.ndarray
    bias_1: np.ndarray
    weights_2: np.ndarray
    bias_2: np.ndarray

    @classmethod
    def random(cls, rng: np.random.Generator, hue: float | None = None) -> "Genome":
        traits = {key: float(rng.uniform(low, high)) for key, (low, high) in TRAIT_BOUNDS.items()}
        if hue is not None:
            traits["hue"] = float(hue % 1.0)
        return cls(
            traits=traits,
            weights_1=rng.normal(0.0, 0.58, (INPUT_COUNT, HIDDEN_COUNT)).astype(np.float32),
            bias_1=rng.normal(0.0, 0.22, HIDDEN_COUNT).astype(np.float32),
            weights_2=rng.normal(0.0, 0.58, (HIDDEN_COUNT, OUTPUT_COUNT)).astype(np.float32),
            bias_2=rng.normal(0.0, 0.22, OUTPUT_COUNT).astype(np.float32),
        )

    def mutated(self, rng: np.random.Generator, rate: float, scale: float) -> "Genome":
        effective_rate = float(np.clip((rate + self.traits["mutation_rate"]) * 0.5, 0.0, 0.4))
        traits: dict[str, float] = {}
        for key in TRAIT_BOUNDS:
            value = self.traits[key]
            low, high = TRAIT_BOUNDS[key]
            span = high - low
            change = rng.normal(0.0, scale * span) if rng.random() < effective_rate else 0.0
            traits[key] = float(np.clip(value + change, low, high))

        def mutate_array(array: np.ndarray) -> np.ndarray:
            mask = rng.random(array.shape) < effective_rate
            noise = rng.normal(0.0, scale, array.shape)
            return np.clip(array + mask * noise, -3.0, 3.0).astype(np.float32)

        return Genome(
            traits,
            mutate_array(self.weights_1),
            mutate_array(self.bias_1),
            mutate_array(self.weights_2),
            mutate_array(self.bias_2),
        )

    def distance(self, other: "Genome") -> float:
        trait_distances = []
        for key in TRAIT_BOUNDS:
            value = self.traits[key]
            low, high = TRAIT_BOUNDS[key]
            trait_distances.append(abs(value - other.traits[key]) / (high - low))
        trait_component = float(np.mean(trait_distances))
        neural_component = float(
            np.mean(np.abs(self.weights_1 - other.weights_1))
            + np.mean(np.abs(self.weights_2 - other.weights_2))
        ) / 6.0
        return 0.7 * trait_component + 0.3 * neural_component

    def to_dict(self) -> dict[str, Any]:
        return {
            "traits": self.traits,
            "weights_1": self.weights_1.tolist(),
            "bias_1": self.bias_1.tolist(),
            "weights_2": self.weights_2.tolist(),
            "bias_2": self.bias_2.tolist(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Genome":
        genome = cls(
            traits={key: float(data["traits"][key]) for key in TRAIT_BOUNDS},
            weights_1=np.asarray(data["weights_1"], dtype=np.float32),
            bias_1=np.asarray(data["bias_1"], dtype=np.float32),
            weights_2=np.asarray(data["weights_2"], dtype=np.float32),
            bias_2=np.asarray(data["bias_2"], dtype=np.float32),
        )
        if genome.weights_1.shape != (INPUT_COUNT, HIDDEN_COUNT) or genome.weights_2.shape != (HIDDEN_COUNT, OUTPUT_COUNT):
            raise ValueError("invalid neural-controller shape in saved genome")
        return genome
