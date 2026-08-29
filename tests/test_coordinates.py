import numpy as np
import pytest

from ingestion.coordinates import mirror_lateral, orient_left_to_right, statsbomb_to_canonical


def test_statsbomb_coordinate_conversion():
    assert statsbomb_to_canonical(120, 80) == pytest.approx((100, 100))
    assert statsbomb_to_canonical(60, 40) == pytest.approx((50, 50))


def test_coordinate_validation_and_orientation():
    with pytest.raises(ValueError):
        statsbomb_to_canonical(121, 40)
    assert orient_left_to_right(25, 30, False) == (75, 70)


def test_pitch_mirroring():
    grid = np.arange(12).reshape(3, 4)
    assert np.array_equal(mirror_lateral(grid), grid[:, ::-1])
