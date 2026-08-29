import pandas as pd

from ingestion.wyscout import _appearance_rows
from similarity.metrics import per90
from similarity.search import rank_similar


def test_literal_null_substitution_source_edge_is_safe():
    match = {
        "wyId": 123,
        "teamsData": {
            "7": {
                "formation": {
                    "substitutions": "null",
                    "lineup": [{"playerId": 9}],
                    "bench": [],
                }
            }
        },
    }
    rows = _appearance_rows(match)
    assert len(rows) == 1
    assert rows[0]["minutes"] == 90
    assert rows[0]["start"] is True


def test_per90_preserves_unavailable_and_handles_scale():
    assert per90(10, 900) == 1.0
    assert per90(None, 900) is None
    assert per90(3, 0) is None


def test_minimum_minute_filter_is_applied_before_search():
    vector = [1.0] + [0.0] * 11
    frame = pd.DataFrame(
        [
            {
                "player_season_id": "reference",
                "minutes": 1000,
                "grid_x": 3,
                "grid_y": 4,
                "fp_all_actions": vector,
            },
            {
                "player_season_id": "eligible",
                "minutes": 900,
                "grid_x": 3,
                "grid_y": 4,
                "fp_all_actions": vector,
            },
            {
                "player_season_id": "too_few",
                "minutes": 100,
                "grid_x": 3,
                "grid_y": 4,
                "fp_all_actions": vector,
            },
        ]
    )
    results = rank_similar(frame, "reference", {"Spatial role": 1}, min_minutes=500)
    assert results["player_season_id"].tolist() == ["eligible"]
