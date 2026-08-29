from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.spatial.distance import jensenshannon


def probability_grid(points: np.ndarray, grid: tuple[int, int] = (16, 12)) -> np.ndarray:
    """Return a unit-mass x-by-y grid from canonical coordinate pairs."""
    if points.size == 0:
        return np.zeros(grid, dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("points must have shape (n, 2)")
    if np.any(points < 0) or np.any(points > 100):
        raise ValueError("points must be within canonical 0..100 pitch")
    histogram, _, _ = np.histogram2d(
        points[:, 0], points[:, 1], bins=grid, range=((0, 100), (0, 100))
    )
    mass = histogram.sum()
    return (histogram / mass if mass else histogram).astype(np.float32)


def cosine_score(a: np.ndarray, b: np.ndarray) -> float:
    av, bv = a.ravel().astype(float), b.ravel().astype(float)
    denominator = np.linalg.norm(av) * np.linalg.norm(bv)
    return float(np.dot(av, bv) / denominator) if denominator else 0.0


def js_score(a: np.ndarray, b: np.ndarray) -> float:
    av, bv = a.ravel().astype(float), b.ravel().astype(float)
    if not av.sum() or not bv.sum():
        return 0.0
    return float(1.0 - jensenshannon(av, bv, base=2.0))


@lru_cache(maxsize=8)
def ground_cost(grid: tuple[int, int]) -> np.ndarray:
    xs = (np.arange(grid[0]) + 0.5) * (100 / grid[0])
    ys = (np.arange(grid[1]) + 0.5) * (100 / grid[1])
    locations = np.array(np.meshgrid(xs, ys, indexing="ij")).reshape(2, -1).T
    delta = locations[:, None, :] - locations[None, :, :]
    return np.sqrt(np.sum(delta * delta, axis=2))


@lru_cache(maxsize=2048)
def _sinkhorn_self_cost(serialized: bytes, grid: tuple[int, int], regularization: float) -> float:
    import ot

    vector = np.frombuffer(serialized, dtype=np.float64)
    return float(ot.sinkhorn2(vector, vector, ground_cost(grid), regularization))


def sinkhorn_distance(a: np.ndarray, b: np.ndarray, regularization: float = 6.0) -> float:
    if not a.sum() or not b.sum():
        return 100.0
    try:
        import ot

        # A tiny common floor avoids divisions by zero in Sinkhorn iterations
        # without materially changing any occupied cell's probability mass.
        av, bv = a.ravel().astype(float), b.ravel().astype(float)
        av = (av + 1e-10) / (av.sum() + 1e-10 * av.size)
        bv = (bv + 1e-10) / (bv.sum() + 1e-10 * bv.size)
        cost = ground_cost(a.shape)
        cross = float(ot.sinkhorn2(av, bv, cost, regularization))
        # Mirroring has identical self-cost on a symmetric pitch, so canonical
        # keys share the cached value across same-side and mirror comparisons.
        av_mirror = av.reshape(a.shape)[:, ::-1].copy().ravel()
        bv_mirror = bv.reshape(b.shape)[:, ::-1].copy().ravel()
        key_a = min(av.tobytes(), av_mirror.tobytes())
        key_b = min(bv.tobytes(), bv_mirror.tobytes())
        self_a = _sinkhorn_self_cost(key_a, a.shape, regularization)
        self_b = _sinkhorn_self_cost(key_b, b.shape, regularization)
        # Sinkhorn divergence removes entropic self-cost: identical means zero.
        return max(0.0, cross - 0.5 * self_a - 0.5 * self_b)
    except ImportError:
        from scipy.stats import wasserstein_distance

        x = np.linspace(0, 100, a.shape[0])
        y = np.linspace(0, 100, a.shape[1])
        return float(
            np.hypot(
                wasserstein_distance(x, x, a.sum(axis=1), b.sum(axis=1)),
                wasserstein_distance(y, y, a.sum(axis=0), b.sum(axis=0)),
            )
        )


def spatial_score(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    """Blend transport, overlap and distribution-shape similarity into 0..100."""
    cosine = cosine_score(a, b)
    js = js_score(a, b)
    distance = sinkhorn_distance(a, b)
    transport = float(np.exp(-distance / 22.0))
    score = 100.0 * (0.55 * transport + 0.25 * cosine + 0.20 * js)
    return {
        "score": max(0.0, min(100.0, score)),
        "cosine": cosine,
        "jensen_shannon": js,
        "sinkhorn_distance": distance,
        "transport_similarity": transport,
    }


def mirrored(grid: np.ndarray) -> np.ndarray:
    return np.flip(grid, axis=1).copy()


def role_scores(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    same = spatial_score(reference, candidate)["score"]
    mirror = spatial_score(reference, mirrored(candidate))["score"]
    return {"same_side": same, "mirrored": mirror, "role": max(same, mirror)}
