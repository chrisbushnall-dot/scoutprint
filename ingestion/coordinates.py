from __future__ import annotations

import numpy as np


def statsbomb_to_canonical(x: float, y: float) -> tuple[float, float]:
    """Convert StatsBomb 120x80 coordinates to canonical 0..100 coordinates.

    StatsBomb open event locations are supplied in the acting team's attacking
    perspective, so no half-specific x flip is applied for this provider.
    """
    if not (0 <= x <= 120 and 0 <= y <= 80):
        raise ValueError(f"StatsBomb coordinate out of range: {(x, y)}")
    return x * (100.0 / 120.0), y * (100.0 / 80.0)


def orient_left_to_right(x: float, y: float, attacks_right: bool) -> tuple[float, float]:
    if not (0 <= x <= 100 and 0 <= y <= 100):
        raise ValueError(f"Canonical coordinate out of range: {(x, y)}")
    return (x, y) if attacks_right else (100.0 - x, 100.0 - y)


def mirror_lateral(vector: np.ndarray) -> np.ndarray:
    """Mirror a 2-D pitch grid across the longitudinal centre line."""
    if vector.ndim != 2:
        raise ValueError("Expected a 2-D grid")
    return np.flip(vector, axis=1).copy()
