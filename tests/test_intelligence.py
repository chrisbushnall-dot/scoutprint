import json

import numpy as np
import pandas as pd

from similarity.intelligence import ROLE_TAXONOMY, build_player_intelligence


def profile(
    player_id: str,
    season: int,
    *,
    position: str,
    metrics: dict[str, float] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "is_primary_profile": True,
        "player_season_id": f"{player_id}-{season}",
        "canonical_player_id": player_id,
        "canonical_person_id": player_id,
        "player_name": player_id,
        "team_name": "Test FC",
        "competition_name": "Test League",
        "season_name": f"{season}/{str(season + 1)[-2:]}",
        "season_start_year": season,
        "source_provider": "test",
        "source_preference_rank": 1,
        "positions": position,
        "data_tier": "A",
        "comparison_coverage": 100,
        "minutes": 1800,
        "age": 20,
        "fp_all_actions": np.full(96, 1 / 96),
    }
    if metrics:
        row.update(metrics)
    return row


def test_behaviour_leads_role_and_scores_remain_transparent():
    rows = [
        profile(
            "scorer",
            2024,
            position="Forward",
            metrics={
                "goals_p90": 0.9,
                "xg_p90": 0.8,
                "shots_p90": 4.5,
                "box_presence_rate": 0.8,
                "pct_penalty_area": 0.8,
                "pct_central": 0.8,
            },
        ),
        profile(
            "creator",
            2024,
            position="Forward",
            metrics={
                "assists_p90": 0.5,
                "xa_p90": 0.55,
                "chance_creation_p90": 4.0,
                "progressions_p90": 8.0,
                "carries_p90": 7.0,
                "dribbles_p90": 3.0,
                "pct_wide": 0.8,
            },
        ),
    ]
    output = build_player_intelligence(pd.DataFrame(rows)).set_index("canonical_player_id")

    assert output.loc["scorer", "primary_role"] in ROLE_TAXONOMY
    assert output.loc["creator", "primary_role"] in ROLE_TAXONOMY
    assert output.loc["scorer", "primary_role"] != output.loc["creator", "primary_role"]
    components = json.loads(output.loc["creator", "radar_components_json"])
    assert set(components) == {
        "current_level",
        "development_velocity",
        "age_context",
        "role_underlying_output",
        "minutes_reliability",
        "data_confidence",
    }
    assert 0 <= output.loc["creator", "radar_score"] <= 100


def test_development_needs_consecutive_comparable_seasons_and_missing_spatial_is_safe():
    metrics = {
        "passes_p90": 30.0,
        "progressions_p90": 4.0,
        "defensive_actions_p90": 3.0,
    }
    rows = [
        profile("riser", 2023, position="Midfield", metrics=metrics),
        profile(
            "riser",
            2024,
            position="Midfield",
            metrics={**metrics, "passes_p90": 55.0, "progressions_p90": 8.0},
        ),
        profile("peer", 2023, position="Midfield", metrics={**metrics, "passes_p90": 60.0}),
        profile("peer", 2024, position="Midfield", metrics=metrics),
    ]
    for row in rows:
        row["fp_all_actions"] = None
    output = build_player_intelligence(pd.DataFrame(rows))
    current = output[
        (output["canonical_player_id"] == "riser")
        & (output["season_start_year"] == 2024)
    ].iloc[0]

    assert pd.notna(current["development"])
    assert current["spatial_change"] is None or pd.isna(current["spatial_change"])
    assert json.loads(current["development_context_json"])["biggest_metric_changes"]


def test_development_rejects_low_minute_baseline_instead_of_scoring_playing_time_growth():
    rows = [
        profile(
            "igor",
            2024,
            position="Centre Forward",
            metrics={"goals_p90": 0.0, "xg_p90": 0.14, "shots_p90": 2.14},
        ),
        profile(
            "igor",
            2025,
            position="Centre Forward",
            metrics={"goals_p90": 0.57, "xg_p90": 1.06, "shots_p90": 4.32},
        ),
        profile(
            "peer",
            2024,
            position="Centre Forward",
            metrics={"goals_p90": 0.4, "xg_p90": 0.5, "shots_p90": 3.0},
        ),
        profile(
            "peer",
            2025,
            position="Centre Forward",
            metrics={"goals_p90": 0.4, "xg_p90": 0.5, "shots_p90": 3.0},
        ),
    ]
    rows[0]["minutes"] = 168
    rows[1]["minutes"] = 3499
    output = build_player_intelligence(pd.DataFrame(rows))
    current = output[
        (output["canonical_player_id"] == "igor")
        & (output["season_start_year"] == 2025)
    ].iloc[0]

    assert pd.isna(current["development"])
    context = json.loads(current["development_context_json"])
    assert context["status"] == "unavailable"
    assert context["minimum_minutes_per_season"] == 900
    assert context["previous_minutes"] == 168


def test_development_uses_underlying_performance_and_weaker_sample_reliability():
    rows = [
        profile(
            "riser",
            2023,
            position="Midfield",
            metrics={"passes_p90": 30.0, "progressions_p90": 4.0},
        ),
        profile(
            "riser",
            2024,
            position="Midfield",
            metrics={"passes_p90": 60.0, "progressions_p90": 8.0},
        ),
        profile(
            "peer",
            2023,
            position="Midfield",
            metrics={"passes_p90": 60.0, "progressions_p90": 8.0},
        ),
        profile(
            "peer",
            2024,
            position="Midfield",
            metrics={"passes_p90": 30.0, "progressions_p90": 4.0},
        ),
    ]
    rows[0]["minutes"] = 900
    output = build_player_intelligence(pd.DataFrame(rows))
    current = output[
        (output["canonical_player_id"] == "riser")
        & (output["season_start_year"] == 2024)
    ].iloc[0]

    assert current["development"] == round(
        current["development_raw"] * current["development_reliability"], 2
    )
    assert current["development_reliability"] < 1
    context = json.loads(current["development_context_json"])
    assert context["status"] == "comparable"
    assert "sample-reliability adjusted" in context["method"]


def test_profiles_without_behaviour_are_explicitly_unclassified():
    output = build_player_intelligence(
        pd.DataFrame([profile("unknown", 2024, position="Forward")])
    ).iloc[0]

    assert output["primary_role"] == "Unclassified"
    assert output["role_confidence"] == "LOW"
    assert output["current_level"] is None or pd.isna(output["current_level"])
    assert "No behavioural metrics" in output["role_evidence_json"]


def test_mls_next_pro_is_excluded_before_intelligence_population_scoring():
    senior = profile(
        "senior",
        2025,
        position="Forward",
        metrics={"goals_p90": 0.4, "xg_p90": 0.45, "shots_p90": 2.8},
    )
    excluded = profile(
        "next-pro",
        2025,
        position="Forward",
        metrics={"goals_p90": 4.0, "xg_p90": 3.5, "shots_p90": 12.0},
    )
    excluded["competition_name"] = " MLS NEXT Pro "

    output = build_player_intelligence(pd.DataFrame([senior, excluded]))

    assert output["canonical_player_id"].tolist() == ["senior"]
    assert "MLS NEXT Pro" not in output["competition_name"].tolist()
