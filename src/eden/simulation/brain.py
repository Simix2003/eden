from __future__ import annotations

import numpy as np

from eden.constants import INPUT_COUNT
from eden.simulation.genome import Genome


def decide(genome: Genome, sensors: np.ndarray, instinct_bias: np.ndarray | None = None) -> tuple[int, np.ndarray]:
    if sensors.shape != (INPUT_COUNT,):
        raise ValueError(f"expected {INPUT_COUNT} sensors, got {sensors.shape}")
    hidden = np.tanh(sensors @ genome.weights_1 + genome.bias_1)
    outputs = np.tanh(hidden @ genome.weights_2 + genome.bias_2)
    if instinct_bias is not None:
        outputs = outputs + instinct_bias
    return int(np.argmax(outputs)), outputs

