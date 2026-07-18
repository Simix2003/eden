from __future__ import annotations

from typing import Any
import numpy as np


def make_rng(seed: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(seed))


def smooth_field(rng: np.random.Generator, shape: tuple[int, int], coarse: int = 12) -> np.ndarray:
    """Create cheap coherent noise without a SciPy dependency."""
    height, width = shape
    ch = max(3, (height + coarse - 1) // coarse)
    cw = max(3, (width + coarse - 1) // coarse)
    small = rng.random((ch, cw), dtype=np.float32)
    field = np.repeat(np.repeat(small, coarse, axis=0), coarse, axis=1)[:height, :width]
    for _ in range(max(2, coarse // 2)):
        field = (
            field * 4.0
            + np.roll(field, 1, 0)
            + np.roll(field, -1, 0)
            + np.roll(field, 1, 1)
            + np.roll(field, -1, 1)
        ) / 8.0
    minimum = float(field.min())
    span = max(1e-7, float(field.max()) - minimum)
    return ((field - minimum) / span).astype(np.float32)


def rng_state(rng: np.random.Generator) -> dict[str, Any]:
    return rng.bit_generator.state


def restore_rng(state: dict[str, Any]) -> np.random.Generator:
    rng = make_rng(0)
    rng.bit_generator.state = state
    return rng

