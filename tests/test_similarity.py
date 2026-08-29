import numpy as np

from similarity.spatial import probability_grid, role_scores, spatial_score


def cloud(x: float, y: float, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.clip(rng.normal((x, y), (2.0, 2.0), size=(500, 2)), 0, 100)


def test_probability_grid_is_unit_mass():
    grid = probability_grid(cloud(70, 40))
    assert np.isclose(grid.sum(), 1.0)


def test_identical_and_displaced_heatmaps_behave_spatially():
    reference = probability_grid(cloud(75, 25))
    identical = spatial_score(reference, reference)["score"]
    near = spatial_score(reference, probability_grid(cloud(77, 25)))["score"]
    far = spatial_score(reference, probability_grid(cloud(25, 75)))["score"]
    assert identical > 99
    assert near > far + 25
    assert far < 60


def test_mirror_mode_recovers_opposite_flank_role():
    right = probability_grid(cloud(78, 22))
    left = probability_grid(cloud(78, 78))
    scores = role_scores(right, left)
    assert scores["mirrored"] > 95
    assert scores["mirrored"] > scores["same_side"] + 25
