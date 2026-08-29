from __future__ import annotations


def per90(value: float | None, minutes: float | None) -> float | None:
    """Convert a count/value to per-90 without inventing unavailable data."""
    if value is None or minutes is None or minutes <= 0:
        return None
    return float(value) * 90.0 / float(minutes)
