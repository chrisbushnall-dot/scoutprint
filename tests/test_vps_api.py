from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

import vps_api.main as api_module
from similarity.roles import add_role_compatibility
from vps_api.main import ExactScoutprintService, PitchApiMatchService, app


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
        "shots_available": spatial,
        "chance_creation_available": spatial,
        "fp_shots": grid.ravel().tolist() if spatial else None,
        "fp_goals": grid.ravel().tolist() if spatial else None,
        "fp_chance_creation": grid.ravel().tolist() if spatial else None,
        "count_all_actions": 120 if spatial else None,
        "count_shots": 24 if spatial else None,
        "count_chance_creation": 18 if spatial else None,
        "goals_p90": 0.5,
        "xg_p90": 0.48,
        "shots_p90": 2.4,
        "assists_p90": 0.2,
        "xa_p90": 0.23,
        "chance_creation_p90": 1.8,
        "pct_penalty_area": 0.21 if spatial else None,
        "box_presence_rate": 0.14 if spatial else None,
        "xg_definition": "Fixture expected goals",
        "chance_creation_definition": "Fixture created shots",
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
    service.intelligence_frame = pd.DataFrame(
        [
            {
                "player_season_id": "candidate",
                "canonical_person_id": "canonical:candidate",
                "player_name": "Candidate Player",
                "team_name": "Test FC",
                "competition_name": "Test League",
                "season_name": "2023/24",
                "candidate_window": "2023/24",
                "positions": "Forward",
                "age": 21.0,
                "minutes": 1_800.0,
                "data_tier": "A",
                "primary_role": "Inside Forward",
                "secondary_role": None,
                "role_group": "Attack",
                "role_confidence": "HIGH",
                "role_confidence_score": 78.0,
                "role_evidence_json": '{"dimensions":[{"dimension":"Scoring"}]}',
                "metric_coverage": 0.8,
                "current_level": 73.2,
                "current_level_raw": 75.0,
                "current_level_components_json": '{"xg_p90":81.0}',
                "league_population": 200,
                "league_population_factor": 0.96,
                "sample_factor": 1.0,
                "career_seasons": 2,
                "confidence_score": 82.0,
                "confidence_label": "HIGH",
                "previous_season_year": 2022,
                "previous_current_level": 65.0,
                "previous_role": "Wide Creator",
                "previous_team": "Previous FC",
                "previous_league": "Test League",
                "development": 8.2,
                "development_context_json": '{"team_change":true}',
                "role_changed": True,
                "spatial_change": None,
                "xg_change": 0.12,
                "xa_change": 0.03,
                "minutes_change": 300.0,
                "underlying_output_label": "Production Lag",
                "output_gap": 0.17,
                "goals_p90": 0.31,
                "assists_p90": 0.2,
                "xg_p90": 0.48,
                "xa_p90": 0.23,
                "spatial_available": False,
                "xg_available": True,
                "xa_available": True,
                "radar_score": 76.4,
                "breakout_score": 81.3,
                "radar_components_json": '{"current_level":73.2}',
            }
        ]
    )
    service.intelligence_by_id = service.intelligence_frame.set_index(
        "player_season_id", drop=False
    )
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


def test_derived_intelligence_catalogue_and_player_payload_are_private(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"X-Scoutprint-API-Key": "test-server-secret"}
    assert client.get("/intelligence/catalogue").status_code == 401
    catalogue = client.get("/intelligence/catalogue", headers=headers)
    assert catalogue.status_code == 200
    assert catalogue.json()["player_seasons"] == 1
    assert catalogue.json()["development_available"] == 1
    assert catalogue.json()["roles"] == {"Inside Forward": 1}
    assert catalogue.json()["seasons"] == ["2023/24"]
    assert catalogue.json()["leagues"] == ["Test League"]
    assert catalogue.json()["positions"] == ["Forward"]
    assert "player_name" in catalogue.json()["player_sort_fields"]

    response = client.get("/player/candidate/intelligence", headers=headers)
    assert response.status_code == 200
    intelligence = response.json()["intelligence"]
    assert intelligence["current_level_components"] == {"xg_p90": 81.0}
    assert intelligence["radar_components"] == {"current_level": 73.2}
    assert intelligence["spatial_available"] is False
    evidence = intelligence["dossier_evidence"]
    assert evidence["grid"] == [12, 8]
    assert evidence["spatial"]["map_available"] is True
    assert evidence["shooting"]["metrics"]["shots_p90"] == 2.4
    assert evidence["creation"]["event_count"] == 18
    assert "fp_shots" not in evidence["shooting"]
    assert "fp_all_actions" not in intelligence
    assert client.get("/player/missing/intelligence", headers=headers).status_code == 404


def test_player_intelligence_includes_ordered_canonical_development_history(
    monkeypatch,
) -> None:
    service = _service()
    current = service.intelligence_frame.iloc[0].to_dict()
    previous = {
        **current,
        "player_season_id": "candidate-previous",
        "season_name": "2022/23",
        "candidate_window": "2022/23",
        "team_name": "Previous FC",
        "primary_role": "Wide Creator",
        "current_level": 65.0,
        "previous_season_year": None,
        "previous_current_level": None,
        "previous_role": None,
        "development": None,
        "development_context_json": None,
        "role_changed": False,
    }
    unrelated = {**previous, "player_season_id": "other", "canonical_person_id": "other"}
    service.intelligence_frame = pd.DataFrame([current, unrelated, previous])
    service.intelligence_by_id = service.intelligence_frame.set_index(
        "player_season_id", drop=False
    )
    monkeypatch.setenv("SCOUTPRINT_API_KEY", "test-server-secret")
    monkeypatch.setattr(api_module, "get_service", lambda: service)

    response = TestClient(app).get(
        "/player/candidate/intelligence",
        headers={"X-Scoutprint-API-Key": "test-server-secret"},
    )
    assert response.status_code == 200
    intelligence = response.json()["intelligence"]
    assert [row["player_season_id"] for row in intelligence["history"]] == [
        "candidate-previous",
        "candidate",
    ]
    assert intelligence["history"][0]["development"] is None
    assert intelligence["history"][1]["previous_role"] == "Wide Creator"


def test_radar_modes_filters_sorting_and_transparent_payload(monkeypatch) -> None:
    service = _service()
    candidate = service.intelligence_frame.iloc[0].to_dict()
    scorer = {
        **candidate,
        "player_season_id": "young-scorer",
        "canonical_person_id": "canonical:young-scorer",
        "player_name": "Young Scorer",
        "team_name": "Other FC",
        "competition_name": "Other League",
        "season_name": "2024/25",
        "candidate_window": "2024/25",
        "positions": "Striker",
        "age": 20.0,
        "primary_role": "Box 9",
        "role_group": "Attack",
        "confidence_label": "MEDIUM",
        "development": None,
        "role_changed": False,
        "underlying_output_label": "In Line",
        "output_gap": 0.0,
        "xg_p90": 0.8,
        "xa_p90": 0.05,
        "radar_score": 88.0,
        "breakout_score": 95.0,
    }
    riser = {
        **candidate,
        "player_season_id": "midfield-riser",
        "canonical_person_id": "canonical:midfield-riser",
        "player_name": "Midfield Riser",
        "age": 24.0,
        "positions": "Central Midfield",
        "primary_role": "Progressive 8",
        "role_group": "Midfield",
        "development": 12.0,
        "role_changed": False,
        "underlying_output_label": "In Line",
        "output_gap": 0.0,
        "xg_p90": 0.1,
        "xa_p90": 0.4,
        "radar_score": 70.0,
        "breakout_score": 65.0,
    }
    service.intelligence_frame = pd.DataFrame([candidate, scorer, riser])
    service.intelligence_by_id = service.intelligence_frame.set_index(
        "player_season_id", drop=False
    )
    monkeypatch.setenv("SCOUTPRINT_API_KEY", "test-server-secret")
    monkeypatch.setattr(api_module, "get_service", lambda: service)
    client = TestClient(app)
    headers = {"X-Scoutprint-API-Key": "test-server-secret"}

    assert client.get("/radar").status_code == 401
    response = client.get("/radar?minimum_minutes=1000", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert [row["player_season_id"] for row in payload["results"]] == ["young-scorer"]
    assert payload["sort"] == {"field": "breakout_score", "order": "desc"}
    assert payload["score_model"]["radar_weights"]["current_performance"] == 0.58
    assert payload["ranking_window"] == "current_3_seasons"
    assert payload["ranking_seasons"] == ["2024/25", "2023/24", "2022/23"]
    assert payload["results"][0]["radar_components"] == {"current_level": 73.2}

    filtered = client.get(
        "/radar?mode=biggest-risers&season=2023/24&league=Test%20League"
        "&minimum_age=20&maximum_age=22&role=Inside%20Forward&position=forward"
        "&minimum_minutes=1500&confidence=high",
        headers=headers,
    ).json()
    assert filtered["total"] == 1
    assert filtered["results"][0]["player_season_id"] == "candidate"
    assert filtered["filters"]["confidence"] == "HIGH"

    assert [
        row["player_season_id"]
        for row in client.get("/radar?mode=u21", headers=headers).json()["results"]
    ] == ["young-scorer"]
    assert client.get("/radar?mode=underlying-output", headers=headers).json()["total"] == 0
    assert client.get("/radar?mode=role-changes", headers=headers).json()["total"] == 0
    assert client.get("/radar?mode=midfield", headers=headers).json()["total"] == 0
    age_sorted = client.get(
        "/radar?sort_by=age&sort_order=asc&limit=2", headers=headers
    ).json()
    assert [row["age"] for row in age_sorted["results"]] == [20.0]
    assert age_sorted["total"] == 1

    assert client.get("/radar?mode=unknown", headers=headers).status_code == 422
    assert client.get("/radar?sort_by=unknown", headers=headers).status_code == 422


def test_default_radar_is_current_three_season_collective_and_explicit_season_is_historical(
    monkeypatch,
) -> None:
    service = _service()
    template = service.intelligence_frame.iloc[0].to_dict()

    def row(
        player_season_id: str,
        canonical_id: str,
        season: str,
        *,
        raw_year: int,
        score: float,
        current: float,
        xg: float,
        xa: float,
        output_gap: float,
        development: float | None,
        confidence: float,
        age: float = 24.0,
        team: str = "Current FC",
        role_changed: bool = False,
        underlying: str = "In Line",
    ) -> dict[str, object]:
        return {
            **template,
            "player_season_id": player_season_id,
            "canonical_person_id": canonical_id,
            "player_name": "Current Player" if canonical_id == "current" else canonical_id,
            "team_name": team,
            "season_name": season,
            "candidate_window": season,
            "season_start_year": raw_year,
            "age": age,
            "primary_role": "Inside Forward",
            "role_group": "Attack",
            "confidence_score": confidence,
            "confidence_label": "HIGH",
            "minutes": 1800.0,
            "radar_score": score,
            "breakout_score": score,
            "current_level": current,
            "xg_p90": xg,
            "xa_p90": xa,
            "output_gap": output_gap,
            "development": development,
            "role_changed": role_changed,
            "underlying_output_label": underlying,
        }

    rows = [
        row(
            "current-2023",
            "current",
            "2023/24",
            raw_year=2023,
            score=10.0,
            current=30.0,
            xg=0.10,
            xa=0.20,
            output_gap=0.30,
            development=4.0,
            confidence=70.0,
        ),
        row(
            "current-2024",
            "current",
            "2024/25",
            raw_year=2024,
            score=20.0,
            current=50.0,
            xg=0.20,
            xa=0.40,
            output_gap=0.50,
            development=6.0,
            confidence=80.0,
        ),
        row(
            "current-2025",
            "current",
            "2025/26",
            raw_year=2025,
            score=30.0,
            current=70.0,
            xg=0.30,
            xa=0.60,
            output_gap=0.70,
            development=8.0,
            confidence=90.0,
            age=25.0,
            team="Latest FC",
        ),
        # Highest confidence wins the duplicate latest-season profile, even if its score is
        # lower than another source's value.
        row(
            "current-2025-best",
            "current",
            "2025/26",
            raw_year=2025,
            score=35.0,
            current=70.0,
            xg=0.30,
            xa=0.60,
            output_gap=0.70,
            development=8.0,
            confidence=95.0,
            age=25.0,
            team="Best Latest FC",
        ),
        row(
            "current-2025-ignored",
            "current",
            "2025/26",
            raw_year=2025,
            score=999.0,
            current=99.0,
            xg=9.99,
            xa=9.99,
            output_gap=9.99,
            development=99.0,
            confidence=94.0,
        ),
        row(
            "stale-asano-2023",
            "asano",
            "2023/24",
            raw_year=2023,
            score=10000.0,
            current=10000.0,
            xg=10.0,
            xa=10.0,
            output_gap=10.0,
            development=1000.0,
            confidence=99.0,
        ),
        # ASA's provider year is 2026, but its normalized product window is 2025/26.
        row(
            "asa-2026-raw",
            "asa-current",
            "2026",
            raw_year=2026,
            score=40.0,
            current=60.0,
            xg=0.40,
            xa=0.50,
            output_gap=0.20,
            development=None,
            confidence=80.0,
            team="Mallorca",
        )
    ]
    rows[-1]["candidate_window"] = "2025/26"
    service.intelligence_frame = pd.DataFrame(rows)
    service.intelligence_by_id = service.intelligence_frame.set_index(
        "player_season_id", drop=False
    )
    monkeypatch.setenv("SCOUTPRINT_API_KEY", "test-server-secret")
    monkeypatch.setattr(api_module, "get_service", lambda: service)
    client = TestClient(app)
    headers = {"X-Scoutprint-API-Key": "test-server-secret"}

    payload = client.get("/radar", headers=headers).json()
    by_name = {item["canonical_player_id"]: item for item in payload["results"]}
    assert "asano" not in by_name
    assert by_name["current"]["player_season_id"] == "current-2025-best"
    assert by_name["current"]["radar_score"] == 25.5
    assert by_name["current"]["current_level"] == 56.0
    assert by_name["current"]["xg_p90"] == 0.23
    assert by_name["current"]["development"] == 7.25
    assert by_name["current"]["club"] == "Best Latest FC"
    assert by_name["current"]["ranking_season_count"] == 3
    assert by_name["asa-current"]["ranking_season_count"] == 1
    assert payload["ranking_window"] == "current_3_seasons"
    assert payload["ranking_seasons"] == ["2025/26", "2024/25", "2023/24"]
    assert by_name["asa-current"]["player_season_id"] == "asa-2026-raw"

    explicit = client.get("/radar?season=2023/24", headers=headers).json()
    explicit_ids = {item["player_season_id"] for item in explicit["results"]}
    assert "stale-asano-2023" in explicit_ids
    assert explicit["ranking_window"] == "single_season"
    stale = next(
        item for item in explicit["results"] if item["player_season_id"] == "stale-asano-2023"
    )
    assert stale["radar_score"] == 10000.0

    explicit_latest = client.get("/radar?season=2025/26", headers=headers).json()
    assert [
        item["canonical_player_id"] for item in explicit_latest["results"]
    ].count("current") == 1


def test_default_radar_modes_require_current_supported_evidence(monkeypatch) -> None:
    service = _service()
    template = service.intelligence_frame.iloc[0].to_dict()

    def mode_row(player_id: str, season: str, **values: object) -> dict[str, object]:
        return {
            **template,
            "player_season_id": player_id,
            "canonical_person_id": player_id,
            "player_name": player_id,
            "season_name": season,
            "candidate_window": season,
            "season_start_year": int(season[:4]),
            "confidence_score": 80.0,
            "confidence_label": "HIGH",
            **values,
        }

    rows = [
        mode_row(
            "old-rise-current-no-rise",
            "2023/24",
            development=10.0,
            role_changed=False,
            underlying_output_label="In Line",
            output_gap=0.0,
            age=20.0,
        ),
        mode_row(
            "old-rise-current-no-rise",
            "2025/26",
            development=None,
            role_changed=False,
            underlying_output_label="In Line",
            output_gap=0.0,
            age=25.0,
        ),
        mode_row(
            "old-role-current-stable",
            "2023/24",
            development=None,
            role_changed=True,
            underlying_output_label="In Line",
            output_gap=0.0,
        ),
        mode_row(
            "old-role-current-stable",
            "2025/26",
            development=None,
            role_changed=False,
            underlying_output_label="In Line",
            output_gap=0.0,
            age=25.0,
        ),
        mode_row(
            "old-gap-current-in-line",
            "2023/24",
            development=None,
            role_changed=False,
            underlying_output_label="Production Lag",
            output_gap=0.5,
        ),
        mode_row(
            "old-gap-current-in-line",
            "2025/26",
            development=None,
            role_changed=False,
            underlying_output_label="In Line",
            output_gap=0.0,
            age=25.0,
        ),
    ]
    service.intelligence_frame = pd.DataFrame(rows)
    service.intelligence_by_id = service.intelligence_frame.set_index(
        "player_season_id", drop=False
    )
    monkeypatch.setenv("SCOUTPRINT_API_KEY", "test-server-secret")
    monkeypatch.setattr(api_module, "get_service", lambda: service)
    client = TestClient(app)
    headers = {"X-Scoutprint-API-Key": "test-server-secret"}

    assert client.get("/radar?mode=biggest-risers", headers=headers).json()["total"] == 0
    assert client.get("/radar?mode=role-changes", headers=headers).json()["total"] == 0
    assert client.get("/radar?mode=underlying-output", headers=headers).json()["total"] == 0
    assert [
        item["player_season_id"]
        for item in client.get("/radar?mode=u21", headers=headers).json()["results"]
    ] == []


def test_league_explorer_returns_nine_boards_and_role_distribution(monkeypatch) -> None:
    service = _service()
    candidate = service.intelligence_frame.iloc[0].to_dict()
    service.intelligence_frame = pd.DataFrame(
        [
            candidate,
            {
                **candidate,
                "player_season_id": "progressor",
                "canonical_person_id": "canonical:progressor",
                "player_name": "Progressor",
                "primary_role": "Progressive 8",
                "role_group": "Midfield",
                "development": 10.0,
                "role_changed": False,
            },
            {
                **candidate,
                "player_season_id": "unclassified",
                "canonical_person_id": "canonical:unclassified",
                "player_name": "Unclassified Player",
                "primary_role": "Unclassified",
                "role_group": "Unclassified",
                "development": None,
                "role_changed": False,
            },
        ]
    )
    monkeypatch.setenv("SCOUTPRINT_API_KEY", "test-server-secret")
    monkeypatch.setattr(api_module, "get_service", lambda: service)
    client = TestClient(app)
    headers = {"X-Scoutprint-API-Key": "test-server-secret"}

    assert client.get("/league?league=Test%20League&season=2023/24").status_code == 401
    response = client.get(
        "/league?league=Test%20League&season=2023/24&minimum_minutes=900",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["player_seasons"] == 3
    assert payload["players"] == 3
    assert payload["classified_roles"] == 2
    assert payload["role_distribution"][0] == {
        "role": "Inside Forward",
        "players": 1,
        "share": 33.3,
    }
    assert [board["id"] for board in payload["leaderboards"]] == [
        "u21",
        "breakouts",
        "risers",
        "attackers",
        "creators",
        "progressors",
        "defenders",
        "underlying-output",
        "role-changes",
    ]
    assert payload["leaderboards"][5]["players"][0]["player_name"] == "Progressor"
    assert client.get(
        "/league?league=Unknown&season=2023/24", headers=headers
    ).status_code == 422


def test_team_explorer_bounds_key_players_breakouts_and_role_depth(monkeypatch) -> None:
    service = _service()
    candidate = service.intelligence_frame.iloc[0].to_dict()
    candidate["age"] = 22.0
    service.intelligence_frame = pd.DataFrame(
        [
            candidate,
            {
                **candidate,
                "player_season_id": "team-mate",
                "canonical_person_id": "canonical:team-mate",
                "player_name": "Team Mate",
                "primary_role": "Progressive 8",
                "role_group": "Midfield",
                "age": 20.0,
                "minutes": 900.0,
                "current_level": 80.0,
                "breakout_score": 90.0,
                "spatial_available": True,
            },
        ]
    )
    monkeypatch.setenv("SCOUTPRINT_API_KEY", "test-server-secret")
    monkeypatch.setattr(api_module, "get_service", lambda: service)
    client = TestClient(app)
    headers = {"X-Scoutprint-API-Key": "test-server-secret"}

    assert client.get("/team?team=Test%20FC&league=Test%20League&season=2023/24").status_code == 401
    assert client.get("/intelligence/catalogue", headers=headers).json()["team_seasons"] == [
        {"team": "Test FC", "league": "Test League", "season": "2023/24"}
    ]
    response = client.get(
        "/team?team=Test%20FC&league=Test%20League&season=2023/24",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["players"] == 2
    assert payload["u21_minutes_share"] == 33.3
    assert payload["key_players"][0]["player_name"] == "Team Mate"
    assert payload["breakouts"][0]["breakout_score"] == 90.0
    assert [item["role"] for item in payload["role_depth"]] == [
        "Inside Forward",
        "Progressive 8",
    ]
    assert "Passing networks and tactical conclusions" in payload["unavailable"]
    assert client.get(
        "/team?team=Missing&league=Test%20League&season=2023/24", headers=headers
    ).status_code == 422


def test_recruitment_role_search_filters_collapses_and_explains_fit(monkeypatch) -> None:
    service = _service()
    candidate = service.intelligence_frame.iloc[0].to_dict()
    service.intelligence_frame = pd.DataFrame(
        [
            candidate,
            {
                **candidate,
                "player_season_id": "candidate-latest",
                "season_name": "2024/25",
                "candidate_window": "2024/25",
                "age": 22.0,
                "minutes": 2_000.0,
                "current_level": 76.0,
            },
            {
                **candidate,
                "player_season_id": "second-candidate",
                "canonical_person_id": "canonical:second",
                "player_name": "Second Candidate",
                "age": 25.0,
                "current_level": 80.0,
                "role_confidence_score": 84.0,
            },
            {
                **candidate,
                "player_season_id": "other-role",
                "canonical_person_id": "canonical:other-role",
                "player_name": "Other Role",
                "primary_role": "Box 9",
            },
        ]
    )
    monkeypatch.setenv("SCOUTPRINT_API_KEY", "test-server-secret")
    monkeypatch.setattr(api_module, "get_service", lambda: service)
    client = TestClient(app)
    headers = {"X-Scoutprint-API-Key": "test-server-secret"}

    assert client.get("/recruitment/roles?role=Inside%20Forward").status_code == 401
    response = client.get(
        "/recruitment/roles?role=Inside%20Forward&league=Test%20League"
        "&minimum_age=20&maximum_age=25&minimum_minutes=1500"
        "&sort_by=role_fit&sort_order=desc",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["player_seasons"] == 3
    assert payload["total"] == 2
    assert [row["player_season_id"] for row in payload["candidates"]] == [
        "second-candidate",
        "candidate-latest",
    ]
    assert payload["role_fit_model"]["components"]["role_separation"] == 0.55
    assert payload["candidates"][0]["role_fit"] == 84.0
    assert payload["candidates"][0]["role_fit_evidence"]["metric_coverage"] == 0.8

    season = client.get(
        "/recruitment/roles?role=Inside%20Forward&season=2023/24",
        headers=headers,
    ).json()
    assert {row["player_season_id"] for row in season["candidates"]} == {
        "candidate",
        "second-candidate",
    }
    assert client.get(
        "/recruitment/roles?role=Inside%20Forward&minimum_age=30&maximum_age=20",
        headers=headers,
    ).status_code == 422
    assert client.get(
        "/recruitment/roles?role=Unknown", headers=headers
    ).status_code == 422
    assert client.get(
        "/recruitment/roles?role=Inside%20Forward&league=Unknown",
        headers=headers,
    ).status_code == 422


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
            "include_low_confidence": True,
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
            "include_low_confidence": True,
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
            "include_low_confidence": True,
        },
    )
    result = response.json()["results"][0]
    assert result["recommendation_score"] < result["profile_match"]
    assert result["confidence"] == "LOW"
    assert result["spatial_match"] is None
    assert all(
        item["dimension"] != "Spatial role" for item in result["top_matching_dimensions"]
    )


def test_low_confidence_is_excluded_by_default_but_can_be_included(monkeypatch) -> None:
    client = _client(monkeypatch)
    request = {
        "reference_player_season_id": "reference",
        "candidate_windows": ["2023/24"],
        "data_tiers": ["C"],
        "weights": {"Goal threat": 35, "Spatial role": 65},
        "minimum_comparison_coverage": 0,
        "minimum_role_compatibility": 0,
    }
    assert client.post(
        "/search/similar",
        headers={"X-Scoutprint-API-Key": "test-server-secret"},
        json=request,
    ).json()["results"] == []
    request["include_low_confidence"] = True
    results = client.post(
        "/search/similar",
        headers={"X-Scoutprint-API-Key": "test-server-secret"},
        json=request,
    ).json()["results"]
    assert results[0]["confidence"] == "LOW"


def test_role_compatibility_explicitly_affects_recommendation_score() -> None:
    common = {
        "Overall": 80.0,
        "Comparable profile coverage": 90.0,
        "minutes": 1_800.0,
        "data_tier": "A",
        "Spatial role": 80.0,
        "Goal threat": 80.0,
        "Shooting": 80.0,
        "Chance creation": 80.0,
        "Carrying": 80.0,
        "Passing": 80.0,
        "Defending": 80.0,
    }
    ranked = pd.DataFrame(
        [{**common, "Role compatibility": 95.0}, {**common, "Role compatibility": 50.0}]
    )
    scored = ExactScoutprintService._add_recommendation_evidence(ranked)
    assert scored.loc[0, "Recommendation"] > scored.loc[1, "Recommendation"]
    assert scored.loc[0, "Overall"] == scored.loc[1, "Overall"] == 80.0
    assert scored.loc[0, "Role recommendation factor"] > scored.loc[1, "Role recommendation factor"]


def test_wide_scoring_reference_prefers_wide_forward_over_box_9() -> None:
    reference = _profile("wide-reference", "Wide Reference", 8, 25, position="Forward")
    wide = _profile("wide-candidate", "Wide Candidate", 8, 23, position="Right Winger")
    box = _profile("box-candidate", "Box Candidate", 8, 23, position="Center Forward")
    for profile, pct_wide, pct_central in (
        (reference, 0.46, 0.16),
        (wide, 0.44, 0.18),
        (box, 0.15, 0.46),
    ):
        profile["pct_wide"] = pct_wide
        profile["pct_central"] = pct_central
        profile["chance_creation_p90"] = 1.0
        profile["passes_p90"] = 25.0
    scored, _ = add_role_compatibility(
        pd.DataFrame([reference, wide, box]), "wide-reference"
    )
    compatibility = scored.set_index("player_season_id")["Role compatibility"]
    assert compatibility["wide-candidate"] > compatibility["box-candidate"]


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


def test_player_explorer_filters_sorts_and_collapses_unique_players(monkeypatch) -> None:
    service = _service()
    candidate = service.intelligence_frame.iloc[0].to_dict()
    service.intelligence_frame = pd.DataFrame(
        [
            candidate,
            {
                **candidate,
                "player_season_id": "candidate-second-season",
                "team_name": "Future FC",
                "season_name": "2024/25",
                "candidate_window": "2024/25",
                "age": 22.0,
                "minutes": 1_900.0,
                "current_level": 74.0,
                "radar_score": 79.0,
            },
            {
                **candidate,
                "player_season_id": "reference",
                "canonical_person_id": "canonical:reference",
                "player_name": "Reference Player",
                "data_tier": "B",
                "confidence_label": "MEDIUM",
                "age": 30.0,
                "current_level": 81.0,
                "radar_score": 90.0,
            },
        ]
    )
    service.intelligence_by_id = service.intelligence_frame.set_index(
        "player_season_id", drop=False
    )
    monkeypatch.setenv("SCOUTPRINT_API_KEY", "test-server-secret")
    monkeypatch.setattr(api_module, "get_service", lambda: service)
    client = TestClient(app)
    headers = {"X-Scoutprint-API-Key": "test-server-secret"}

    payload = client.get("/players?player=Player", headers=headers).json()
    assert payload["player_seasons"] == 3
    assert payload["total"] == 2
    assert [row["player_season_id"] for row in payload["players"]] == [
        "reference",
        "candidate-second-season",
    ]

    filtered = client.get(
        "/players?player=Candidate&club=Future&league=Test%20League&season=2024/25"
        "&minimum_age=22&maximum_age=22&role=Inside%20Forward&position=forward"
        "&minimum_minutes=1800&data_tier=a&confidence=high"
        "&sort_by=current_level&sort_order=asc",
        headers=headers,
    ).json()
    assert filtered["total"] == 1
    assert filtered["players"][0]["player_season_id"] == "candidate-second-season"
    assert filtered["players"][0]["current_level"] == 74.0

    uncollapsed = client.get(
        "/players?player=Candidate&unique_players=false", headers=headers
    ).json()
    assert uncollapsed["total"] == 2
    assert len(uncollapsed["players"]) == 2
    assert client.get("/players?data_tier=d", headers=headers).status_code == 422


def test_pitchapi_match_browse_and_detail_are_safe_projections(tmp_path: Path) -> None:
    directory = tmp_path / "match_data/match=m_test"
    directory.mkdir(parents=True)

    def write(endpoint: str, data: object) -> None:
        (directory / f"{endpoint}.json").write_text(json.dumps({"data": data}))

    write(
        "match",
        {
            "id": "m_test",
            "league": {"id": "league", "name": "Test League", "image_url": "private"},
            "season": "2025/2026",
            "home_team": {"id": "home", "name": "Home FC", "image_url": "private"},
            "away_team": {"id": "away", "name": "Away FC", "image_url": "private"},
            "date": "2026-08-31",
            "status": "finished",
            "score_home": 2,
            "score_away": 1,
            "round_name": "Round 3",
        },
    )
    write(
        "shots",
        {"periods": [{"period": "first_half", "shots": [{
            "id": "shot", "player": {"id": "p1", "name": "Player One"},
            "team_id": "home", "x": 90, "y": 50, "expected_goals": 0.4,
            "is_on_target": True, "is_inside_box": True, "minute": 12,
            "event_type": "Goal",
        }]}]},
    )
    write(
        "lineups",
        {"home": {"formation": "4-3-3", "coach": {"name": "Coach"},
        "starters": [{"player_id": "p1", "name": "Player One"}], "subs": []},
        "away": None},
    )
    write(
        "players",
        [{"player": {"id": "p1", "name": "Player One", "image_url": "private"},
        "team_id": "home", "stats": [{"stats": {"Rating": {
            "key": "rating_title", "stat": {"type": "double", "value": 8.2}
        }}}]}],
    )
    service = PitchApiMatchService(tmp_path)
    rows, total = service.browse(
        league="Test League", team="home", date_from=None, date_to=None, offset=0, limit=10
    )
    assert total == 1
    assert rows[0]["availability"]["shots"] is True
    detail = service.detail("m_test")
    assert detail["shot_summary"][0]["xg"] == 0.4
    assert detail["shots"][0]["player"] == {"id": "p1", "name": "Player One"}
    assert detail["top_performers"][0]["stats"]["rating"] == 8.2
    assert detail["lineups"]["home"]["formation"] == "4-3-3"
    assert "image_url" not in json.dumps(detail)
