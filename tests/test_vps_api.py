from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

import vps_api.main as api_module
from vps_api.main import ExactScoutprintService, app


def _profile(
    player_id: str,
    name: str,
    x: int,
    age: float | None,
    *,
    spatial: bool = True,
    canonical_id: str | None = None,
    position: str = "Forward",
    season: str = "2023/24",
    minutes: float = 1_800.0,
) -> dict[str, object]:
    grid = np.zeros((12, 8), dtype=float)
    grid[x, 5] = 1.0
    return {
        "player_season_id": player_id,
        "canonical_player_id": canonical_id or f"canonical:{player_id}",
        "canonical_person_id": canonical_id or f"canonical:{player_id}",
        "player_name": name,
        "team_name": "Test FC",
        "competition_name": "Test League",
        "season_name": season,
        "positions": position,
        "age": age,
        "minutes": minutes,
        "appearances": 25,
        "starts": 20,
        "source_provider": "fixture",
        "data_tier": "A" if spatial else "C",
        "comparison_coverage": 0.9 if spatial else 0.4,
        "season_start_year": 2023,
        "candidate_window": "2023/24",
        "grid_x": 12,
        "grid_y": 8,
        "fp_all_actions": grid.ravel().tolist() if spatial else None,
        "spatial_available": spatial,
        "goals_p90": 0.5,
        "xg_p90": 0.48,
        "pct_penalty_area": 0.21 if spatial else None,
        "box_presence_rate": 0.14 if spatial else None,
    }


def _service() -> ExactScoutprintService:
    service = ExactScoutprintService.__new__(ExactScoutprintService)
    service.frame = pd.DataFrame(
        [
            _profile("reference", "Reference Player", 9, 30),
            _profile("candidate", "Candidate Player", 9, 21),
            _profile(
                "candidate-second-season",
                "Candidate Player",
                9,
                22,
                canonical_id="canonical:candidate",
                season="2024/25",
            ),
            _profile(
                "own-history",
                "Reference Player",
                9,
                31,
                canonical_id="canonical:reference",
                season="2024/25",
            ),
            _profile(
                "defender",
                "Defender Player",
                2,
                24,
                position="Centre Back",
            ),
            _profile("unknown-age", "Unknown Age", 2, None),
            _profile("statistical", "Statistical Player", 0, 20, spatial=False),
        ]
    )
    service.by_id = service.frame.set_index("player_season_id", drop=False)
    return service


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("SCOUTPRINT_API_KEY", "test-server-secret")
    monkeypatch.setattr(api_module, "get_service", _service)
    return TestClient(app)


def test_health_is_public_but_data_requires_server_secret(monkeypatch) -> None:
    client = _client(monkeypatch)
    assert client.get("/health").status_code == 200
    assert client.get("/competitions").status_code == 401
    assert (
        client.get(
            "/competitions", headers={"X-Scoutprint-API-Key": "test-server-secret"}
        ).status_code
        == 200
    )
    catalogue = client.get(
        "/recent/catalogue", headers={"X-Scoutprint-API-Key": "test-server-secret"}
    )
    assert catalogue.status_code == 200
    assert catalogue.json()["recent_player_seasons"] == 7


def test_exact_search_and_age_filter(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/search/similar",
        headers={"X-Scoutprint-API-Key": "test-server-secret"},
        json={
            "reference_player_season_id": "reference",
            "candidate_competitions": ["Test League"],
            "candidate_seasons": ["2023/24"],
            "minimum_age": 18,
            "maximum_age": 23,
            "weights": {"Spatial role": 100},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["engine"] == "EXACT SCOUTPRINT"
    assert payload["authoritative"] is True
    assert [item["player_season_id"] for item in payload["results"]] == ["candidate"]
    assert payload["results"][0]["profile_match"] > 99


def test_comparison_returns_derived_grids_not_raw_events(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/comparison",
        headers={"X-Scoutprint-API-Key": "test-server-secret"},
        json={
            "reference_player_season_id": "reference",
            "candidate_player_season_id": "candidate",
            "weights": {"Spatial role": 100},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["authoritative"] is True
    assert len(payload["reference"]["maps"]["all"]) == 96
    assert payload["difference_maps"]["all"] == [0.0] * 96
    assert "events" not in payload


def test_statistical_tier_c_candidate_is_ranked_without_fake_spatial_score(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/search/similar",
        headers={"X-Scoutprint-API-Key": "test-server-secret"},
        json={
            "reference_player_season_id": "reference",
            "candidate_windows": ["2023/24"],
            "data_tiers": ["C"],
            "weights": {"Goal threat": 100},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert [item["player_season_id"] for item in payload["results"]] == ["statistical"]
    assert payload["results"][0]["data_tier"] == "C"
    assert payload["results"][0]["spatial_match"] is None


def test_same_canonical_player_is_excluded_and_candidate_seasons_collapse(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/search/similar",
        headers={"X-Scoutprint-API-Key": "test-server-secret"},
        json={
            "reference_player_season_id": "reference",
            "candidate_windows": ["2023/24"],
            "minimum_comparison_coverage": 0,
            "minimum_role_compatibility": 0,
        },
    )
    results = response.json()["results"]
    assert all(item["canonical_player_id"] != "canonical:reference" for item in results)
    assert sum(item["canonical_player_id"] == "canonical:candidate" for item in results) == 1


def test_role_incompatible_centre_back_is_filtered(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/search/similar",
        headers={"X-Scoutprint-API-Key": "test-server-secret"},
        json={
            "reference_player_season_id": "reference",
            "candidate_windows": ["2023/24"],
            "minimum_comparison_coverage": 0,
        },
    )
    assert "defender" not in {item["player_season_id"] for item in response.json()["results"]}


def test_low_coverage_adjusts_recommendation_not_raw_similarity(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/search/similar",
        headers={"X-Scoutprint-API-Key": "test-server-secret"},
        json={
            "reference_player_season_id": "reference",
            "candidate_windows": ["2023/24"],
            "data_tiers": ["C"],
            "weights": {"Goal threat": 35, "Spatial role": 65},
            "minimum_comparison_coverage": 0,
            "minimum_role_compatibility": 0,
        },
    )
    result = response.json()["results"][0]
    assert result["recommendation_score"] < result["profile_match"]
    assert result["confidence"] == "LOW"
    assert result["spatial_match"] is None
    assert all(
        item["dimension"] != "Spatial role" for item in result["top_matching_dimensions"]
    )


def test_player_search_groups_profiles_by_canonical_person(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.get(
        "/players?name=Candidate",
        headers={"X-Scoutprint-API-Key": "test-server-secret"},
    )
    players = response.json()["players"]
    assert len(players) == 1
    assert players[0]["profile_count"] == 2
    assert {item["season_name"] for item in players[0]["profiles"]} == {
        "2023/24",
        "2024/25",
    }
