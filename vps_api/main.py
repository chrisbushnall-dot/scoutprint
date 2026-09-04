from __future__ import annotations

import hmac
import json
import math
import os
import re
import threading
import time
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, ClassVar

import numpy as np
import pandas as pd
import polars as pl
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from similarity.roles import add_role_compatibility
from similarity.scope import is_excluded_product_competition
from similarity.search import CATEGORY_METRICS, rank_similar

RADAR_MODES = {
    "breakouts": "Breakouts",
    "biggest-risers": "Biggest Risers",
    "u21": "U21",
    "underlying-output": "Underlying > Output",
    "role-changes": "Role Changes",
    "creators": "Creators",
    "scorers": "Scorers",
    "midfield": "Midfield",
    "defensive": "Defensive",
}

LEAGUE_MODES = {
    "u21": "U21",
    "breakouts": "Breakouts",
    "risers": "Risers",
    "attackers": "Attackers",
    "creators": "Creators",
    "progressors": "Progressors",
    "defenders": "Defenders",
    "underlying-output": "Underlying > Output",
    "role-changes": "Role Changes",
}

LEAGUE_DEFAULT_SORTS = {
    "u21": "radar_score",
    "breakouts": "breakout_score",
    "risers": "development",
    "attackers": "radar_score",
    "creators": "xa_p90",
    "progressors": "current_level",
    "defenders": "current_level",
    "underlying-output": "output_gap",
    "role-changes": "radar_score",
}

INTELLIGENCE_SORT_FIELDS = {
    "radar_score",
    "breakout_score",
    "current_level",
    "development",
    "age",
    "minutes",
    "xg_p90",
    "xa_p90",
    "spatial_change",
    "confidence_score",
    "output_gap",
    "xg_change",
    "xa_change",
    "minutes_change",
}

PLAYER_SORT_FIELDS = {
    **{field: field for field in INTELLIGENCE_SORT_FIELDS},
    "player_name": "player_name",
    "club": "team_name",
    "league": "competition_name",
    "season": "season_name",
    "role": "primary_role",
    "position": "positions",
    "data_tier": "data_tier",
    "confidence": "confidence_label",
}

RECRUITMENT_SORT_FIELDS = {
    "current_level": "current_level",
    "development": "development",
    "role_fit": "role_confidence_score",
    "age": "age",
    "minutes": "minutes",
}

ROLE_FIT_MODEL = {
    "claim": (
        "Evidence strength for the selected behavioural role; not transfer suitability, "
        "ability or potential."
    ),
    "score": "Precomputed behavioural role confidence (0–100).",
    "components": {
        "role_separation": 0.55,
        "available_behaviour_coverage": 0.45,
    },
}

RADAR_DEFAULT_SORTS = {
    "breakouts": "breakout_score",
    "biggest-risers": "development",
    "u21": "radar_score",
    "underlying-output": "output_gap",
    "role-changes": "radar_score",
    "creators": "xa_p90",
    "scorers": "xg_p90",
    "midfield": "radar_score",
    "defensive": "radar_score",
}

RADAR_RECENCY_WEIGHTS = {0: 0.50, 1: 0.30, 2: 0.20}
RADAR_AGGREGATE_FIELDS = {
    "radar_score",
    "breakout_score",
    "current_level",
    "current_level_raw",
    "league_current_performance",
    "league_current_performance_raw",
    "output_gap",
    "goal_gap",
    "assist_gap",
    "goal_gap_p90",
    "assist_gap_p90",
    "expected_gxa_p90",
    "actual_ga_p90",
    "goals_p90",
    "assists_p90",
    "xg_p90",
    "xa_p90",
}

RADAR_SCORE_MODEL = {
    "method_version": "real_world_player_judgement_v1",
    "claim": "Transparent ranking of current evidence; not an ability or potential prediction.",
    "current_performance_definition": (
        "Supported present performance relative to behavioural-role peers, shrunk toward the "
        "neutral peer expectation when role-core evidence or sample reliability is incomplete."
    ),
    "development_definition": (
        "Like-for-like role-component percentile movement across consecutive seasons with at "
        "least 900 minutes in each; compares matched evidence only and reports confidence "
        "separately."
    ),
    "radar_definition": (
        "Evidence-backed analytical interest, not ability, potential or a future-star prediction."
    ),
    "confidence_definition": (
        "Strength of role-core, supporting, spatial and minutes evidence behind the claim."
    ),
    "radar_weights": {
        "current_performance": 0.58,
        "development": 0.16,
        "underlying_performance": 0.08,
        "minutes_reliability": 0.08,
        "evidence_confidence": 0.10,
        "verified_age_bonus": "0 to 8 points",
    },
    "breakout_definition": "Breakouts are ranked directly by Radar Interest.",
}

CREATOR_ROLES = {
    "Linking 9",
    "Wide Creator",
    "Hybrid Scorer-Creator",
    "Second Striker",
    "Creative 10",
    "Progressive 8",
}

SCORER_ROLES = {
    "Box 9",
    "Channel Forward",
    "Inside Forward",
    "Hybrid Scorer-Creator",
    "Second Striker",
}

PROGRESSOR_ROLES = {
    "Progressive 8",
    "Deep Progressor",
    "Controller",
    "Inverted Fullback",
    "Overlapping Fullback",
    "Progressive Centre-Back",
}

INTELLIGENCE_COLUMNS = [
    "player_season_id",
    "canonical_person_id",
    "player_name",
    "source_provider",
    "team_name",
    "competition_name",
    "season_name",
    "season_start_year",
    "positions",
    "age",
    "minutes",
    "data_tier",
    "candidate_window",
    "primary_role",
    "secondary_role",
    "role_group",
    "role_confidence",
    "role_confidence_score",
    "role_evidence_json",
    "metric_coverage",
    "score_method_version",
    "current_level",
    "current_level_raw",
    "current_level_components_json",
    "current_performance_families_json",
    "core_role_coverage",
    "supporting_coverage",
    "spatial_coverage",
    "current_performance_reliability",
    "league_current_performance",
    "league_current_performance_raw",
    "league_population",
    "league_population_factor",
    "sample_factor",
    "career_seasons",
    "confidence_score",
    "confidence_label",
    "previous_season_year",
    "previous_current_level",
    "previous_role",
    "previous_team",
    "previous_league",
    "development",
    "development_confidence",
    "development_confidence_score",
    "development_context_json",
    "role_changed",
    "spatial_change",
    "xg_change",
    "xa_change",
    "minutes_change",
    "underlying_output_label",
    "output_gap",
    "goal_gap",
    "assist_gap",
    "goal_gap_p90",
    "assist_gap_p90",
    "expected_gxa_p90",
    "actual_ga_p90",
    "goals_p90",
    "assists_p90",
    "xg_p90",
    "xa_p90",
    "spatial_available",
    "xg_available",
    "xa_available",
    "radar_score",
    "breakout_score",
    "radar_components_json",
]

DEFAULT_WEIGHTS = {
    "Spatial role": 35.0,
    "Goal threat": 20.0,
    "Shooting": 15.0,
    "Chance creation": 10.0,
    "Carrying": 10.0,
    "Passing": 5.0,
    "Defending": 5.0,
}

PROFILE_FIELDS = [
    "player_season_id",
    "canonical_player_id",
    "player_name",
    "team_name",
    "competition_name",
    "season_name",
    "positions",
    "age",
    "minutes",
    "appearances",
    "starts",
    "source_provider",
    "data_tier",
    "comparison_coverage",
]

STAT_FIELDS = [
    "goals",
    "assists",
    "xg",
    "xa",
    "goals_p90",
    "assists_p90",
    "xg_p90",
    "xa_p90",
    "shots_p90",
    "chance_creation_p90",
    "passes_p90",
    "defensive_actions_p90",
    "progressions_p90",
    "dribbles_p90",
    "carries_p90",
    "receipts_p90",
    "pct_attacking_third",
    "pct_penalty_area",
    "pct_half_space",
    "pct_central",
    "pct_wide",
    "box_presence_rate",
]

MAP_FIELDS = {
    "all": "fp_all_actions",
    "receipts": "fp_receipts",
    "shots": "fp_shots",
    "goals": "fp_goals",
    "chances": "fp_chance_creation",
    "passes": "fp_passes",
    "carries": "fp_carries",
    "progressions": "fp_progressions",
    "dribbles": "fp_dribbles",
    "defence": "fp_defensive_actions",
}

AVAILABILITY_FIELDS = [
    "spatial_available",
    "shots_available",
    "passes_available",
    "chance_creation_available",
    "defending_available",
    "dribbles_available",
    "progressions_available",
    "carries_available",
    "receipts_available",
    "xg_available",
    "xa_available",
    "age_available",
]


class SimilarSearchRequest(BaseModel):
    reference_player_season_id: str
    reference_competition: str | None = None
    reference_season: str | None = None
    candidate_competitions: list[str] = Field(default_factory=list)
    candidate_seasons: list[str] = Field(default_factory=list)
    candidate_windows: list[str] = Field(default_factory=list)
    candidate_positions: list[str] = Field(default_factory=list)
    data_tiers: list[str] = Field(default_factory=lambda: ["A", "B", "C"])
    recent_candidates_only: bool = True
    minimum_minutes: float = Field(default=0, ge=0)
    minimum_age: float | None = Field(default=None, ge=10, le=60)
    maximum_age: float | None = Field(default=None, ge=10, le=60)
    mirror_mode: bool = True
    minimum_comparison_coverage: float = Field(default=40, ge=0, le=100)
    minimum_profile_match: float = Field(default=0, ge=0, le=100)
    minimum_role_compatibility: float = Field(default=42, ge=0, le=100)
    include_low_confidence: bool = False
    unique_players: bool = True
    result_limit: int = Field(default=25, ge=1, le=100)
    exact_shortlist_size: int = Field(default=120, ge=20, le=200)
    weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    @model_validator(mode="after")
    def validate_request(self) -> SimilarSearchRequest:
        if (
            self.minimum_age is not None
            and self.maximum_age is not None
            and self.minimum_age > self.maximum_age
        ):
            raise ValueError("minimum_age must not exceed maximum_age")
        unknown = set(self.weights) - set(DEFAULT_WEIGHTS)
        if unknown:
            raise ValueError(f"Unknown similarity categories: {sorted(unknown)}")
        if any(weight < 0 or weight > 100 for weight in self.weights.values()):
            raise ValueError("Similarity weights must be between 0 and 100")
        if not any(self.weights.values()):
            raise ValueError("At least one similarity weight must be positive")
        if set(self.data_tiers) - {"A", "B", "C"}:
            raise ValueError("data_tiers must contain only A, B or C")
        return self


class ComparisonRequest(SimilarSearchRequest):
    candidate_player_season_id: str


def _safe(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, (list, tuple, np.ndarray)):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, np.ndarray):
        return [_safe(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    return value


class ExactScoutprintService:
    def __init__(self, history_path: Path, intelligence_path: Path):
        self._history_path = history_path
        self._intelligence_path = intelligence_path
        self._refresh_manifest_path = intelligence_path.parent / "refresh_manifest.json"
        self._reload_lock = threading.RLock()
        self._refresh_generation = self._path_signature(self._refresh_manifest_path)
        self.frame, self.by_id = self._load_history(history_path)
        self.intelligence_frame = self._load_intelligence(intelligence_path)
        self.intelligence_by_id = self.intelligence_frame.set_index(
            "player_season_id", drop=False
        )

    @classmethod
    def _load_history(cls, history_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
        if not history_path.exists():
            raise FileNotFoundError(f"Canonical player history not found: {history_path}")
        frame = pl.read_parquet(history_path).to_pandas()
        primary = frame[frame["is_primary_profile"].fillna(False)].copy()
        primary = primary[
            ~primary["competition_name"].map(is_excluded_product_competition)
        ].copy()
        primary = primary.reset_index(drop=True)
        primary["candidate_window"] = primary.apply(cls._candidate_window, axis=1)
        primary["canonical_person_id"] = cls._canonical_person_ids(primary)
        return primary, primary.set_index("player_season_id", drop=False)

    @staticmethod
    def _path_signature(path: Path) -> tuple[int, int] | None:
        if not path.exists():
            return None
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns

    def reload_if_refreshed(self) -> bool:
        """Swap in a fully published refresh generation without restarting the API."""

        generation = self._path_signature(self._refresh_manifest_path)
        if generation is None or generation == self._refresh_generation:
            return False
        with self._reload_lock:
            generation = self._path_signature(self._refresh_manifest_path)
            if generation is None or generation == self._refresh_generation:
                return False
            try:
                frame, by_id = self._load_history(self._history_path)
                intelligence = self._load_intelligence(self._intelligence_path)
            except (FileNotFoundError, OSError, ValueError):
                return False
            intelligence_by_id = intelligence.set_index("player_season_id", drop=False)
            self.frame, self.by_id = frame, by_id
            self.intelligence_frame = intelligence
            self.intelligence_by_id = intelligence_by_id
            self._refresh_generation = generation
            return True

    @staticmethod
    def _load_intelligence(path: Path) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"Derived player intelligence not found: {path}")
        schema = pl.scan_parquet(path).collect_schema()
        missing = sorted(set(INTELLIGENCE_COLUMNS) - set(schema.names()))
        if missing:
            raise ValueError(f"Derived player intelligence is missing columns: {missing}")
        frame = pl.read_parquet(path, columns=INTELLIGENCE_COLUMNS).to_pandas()
        frame = frame[
            ~frame["competition_name"].map(is_excluded_product_competition)
        ].copy()
        if frame.empty:
            raise ValueError("Derived player intelligence is empty")
        if frame["player_season_id"].isna().any() or frame["player_season_id"].duplicated().any():
            raise ValueError("Derived player intelligence has invalid player_season_id values")
        return frame

    @staticmethod
    def _decoded_json(value: Any) -> Any:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        if isinstance(value, str):
            return json.loads(value)
        return _safe(value)

    def intelligence_record(self, row: pd.Series) -> dict[str, Any]:
        return {
            "player_season_id": row["player_season_id"],
            "canonical_player_id": row.get("canonical_person_id"),
            "player_name": row.get("player_name"),
            "source_provider": row.get("source_provider"),
            "club": row.get("team_name"),
            "competition": row.get("competition_name"),
            "season": row.get("season_name"),
            "candidate_window": row.get("candidate_window"),
            "position": row.get("positions"),
            "age": _safe(row.get("age")),
            "minutes": _safe(row.get("minutes")),
            "data_tier": row.get("data_tier"),
            "primary_role": row.get("primary_role"),
            "secondary_role": row.get("secondary_role"),
            "role_group": row.get("role_group"),
            "role_confidence": row.get("role_confidence"),
            "role_confidence_score": _safe(row.get("role_confidence_score")),
            "role_evidence": self._decoded_json(row.get("role_evidence_json")),
            "metric_coverage": _safe(row.get("metric_coverage")),
            "score_method_version": row.get("score_method_version"),
            "current_level": _safe(row.get("current_level")),
            "current_level_raw": _safe(row.get("current_level_raw")),
            "current_level_components": self._decoded_json(
                row.get("current_level_components_json")
            ),
            "current_performance_families": self._decoded_json(
                row.get("current_performance_families_json")
            ),
            "core_role_coverage": _safe(row.get("core_role_coverage")),
            "supporting_coverage": _safe(row.get("supporting_coverage")),
            "spatial_coverage": _safe(row.get("spatial_coverage")),
            "current_performance_reliability": _safe(
                row.get("current_performance_reliability")
            ),
            "league_current_performance": _safe(row.get("league_current_performance")),
            "league_current_performance_raw": _safe(
                row.get("league_current_performance_raw")
            ),
            "league_population": _safe(row.get("league_population")),
            "league_population_factor": _safe(row.get("league_population_factor")),
            "sample_factor": _safe(row.get("sample_factor")),
            "career_seasons": _safe(row.get("career_seasons")),
            "confidence_score": _safe(row.get("confidence_score")),
            "confidence": row.get("confidence_label"),
            "previous_season_year": _safe(row.get("previous_season_year")),
            "previous_current_level": _safe(row.get("previous_current_level")),
            "previous_role": row.get("previous_role"),
            "previous_club": row.get("previous_team"),
            "previous_league": row.get("previous_league"),
            "development": _safe(row.get("development")),
            "development_confidence": row.get("development_confidence"),
            "development_confidence_score": _safe(
                row.get("development_confidence_score")
            ),
            "development_context": self._decoded_json(row.get("development_context_json")),
            "role_changed": bool(_safe(row.get("role_changed")) or False),
            "spatial_change": _safe(row.get("spatial_change")),
            "xg_change": _safe(row.get("xg_change")),
            "xa_change": _safe(row.get("xa_change")),
            "minutes_change": _safe(row.get("minutes_change")),
            "underlying_output_label": row.get("underlying_output_label"),
            "output_gap": _safe(row.get("output_gap")),
            "goal_gap": _safe(row.get("goal_gap")),
            "assist_gap": _safe(row.get("assist_gap")),
            "goal_gap_p90": _safe(row.get("goal_gap_p90")),
            "assist_gap_p90": _safe(row.get("assist_gap_p90")),
            "expected_gxa_p90": _safe(row.get("expected_gxa_p90")),
            "actual_ga_p90": _safe(row.get("actual_ga_p90")),
            "goals_p90": _safe(row.get("goals_p90")),
            "assists_p90": _safe(row.get("assists_p90")),
            "xg_p90": _safe(row.get("xg_p90")),
            "xa_p90": _safe(row.get("xa_p90")),
            "spatial_available": bool(_safe(row.get("spatial_available")) or False),
            "xg_available": bool(_safe(row.get("xg_available")) or False),
            "xa_available": bool(_safe(row.get("xa_available")) or False),
            "radar_score": _safe(row.get("radar_score")),
            "breakout_score": _safe(row.get("breakout_score")),
            "ranking_season_count": _safe(row.get("ranking_season_count")),
            "radar_components": self._decoded_json(row.get("radar_components_json")),
        }

    def intelligence_by_player_season(self, player_season_id: str) -> dict[str, Any]:
        try:
            row = self.intelligence_by_id.loc[player_season_id]
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Player intelligence not found") from error
        record = self.intelligence_record(row)
        canonical_person_id = row.get("canonical_person_id")
        if pd.isna(canonical_person_id):
            history = self.intelligence_frame[
                self.intelligence_frame["player_season_id"] == player_season_id
            ]
        else:
            history = self.intelligence_frame[
                self.intelligence_frame["canonical_person_id"] == canonical_person_id
            ]
        history = history.assign(
            _season_sort=pd.to_numeric(
                history["candidate_window"].fillna(history["season_name"]).str.extract(
                    r"(\d{4})", expand=False
                ),
                errors="coerce",
            )
        ).sort_values(
            ["_season_sort", "competition_name", "player_season_id"],
            ascending=[True, True, True],
            na_position="last",
            kind="stable",
        )
        record["history"] = [
            self.intelligence_record(history_row)
            for _, history_row in history.drop(columns="_season_sort").iterrows()
        ]
        record["dossier_evidence"] = self.dossier_evidence_by_id(player_season_id)
        return record

    def dossier_evidence_by_id(self, player_season_id: str) -> dict[str, Any]:
        """Return only availability-gated, derived evidence needed by dossier views."""
        try:
            row = self.by_id.loc[player_season_id]
        except KeyError:
            return {
                "spatial": {"available": False, "map_available": False},
                "shooting": {"available": False, "map_available": False},
                "creation": {"available": False, "map_available": False},
            }
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        def metric_values(fields: list[str]) -> dict[str, Any]:
            return {field: _safe(row.get(field)) for field in fields}

        def has_value(values: dict[str, Any]) -> bool:
            return any(value is not None for value in values.values())

        grid = [
            int(row["grid_x"]) if pd.notna(row.get("grid_x")) else 12,
            int(row["grid_y"]) if pd.notna(row.get("grid_y")) else 8,
        ]
        spatial_available = bool(_safe(row.get("spatial_available")) or False)
        shots_available = bool(_safe(row.get("shots_available")) or False)
        creation_available = bool(_safe(row.get("chance_creation_available")) or False)

        spatial_map = _safe(row.get("fp_all_actions")) if spatial_available else None
        shot_map = _safe(row.get("fp_shots")) if shots_available else None
        goal_map = _safe(row.get("fp_goals")) if shots_available else None
        creation_map = _safe(row.get("fp_chance_creation")) if creation_available else None
        spatial_metrics = (
            metric_values(
                [
                    "pct_attacking_third",
                    "pct_penalty_area",
                    "pct_half_space",
                    "pct_central",
                    "pct_wide",
                    "box_presence_rate",
                ]
            )
            if spatial_available
            else {}
        )
        shooting_metrics = metric_values(
            ["goals", "xg", "goals_p90", "xg_p90", "shots_p90"]
        )
        creation_metrics = metric_values(
            ["assists", "xa", "assists_p90", "xa_p90", "chance_creation_p90"]
        )

        return {
            "grid": grid,
            "spatial": {
                "available": spatial_available
                and (spatial_map is not None or has_value(spatial_metrics)),
                "map_available": spatial_map is not None,
                "map": spatial_map,
                "event_count": _safe(row.get("count_all_actions")),
                "metrics": spatial_metrics,
            },
            "shooting": {
                "available": has_value(shooting_metrics) or shot_map is not None,
                "map_available": shot_map is not None,
                "maps": {"shots": shot_map, "goals": goal_map},
                "event_count": _safe(row.get("count_shots")),
                "metrics": shooting_metrics,
                "definition": _safe(row.get("xg_definition")),
            },
            "creation": {
                "available": has_value(creation_metrics) or creation_map is not None,
                "map_available": creation_map is not None,
                "map": creation_map,
                "event_count": _safe(row.get("count_chance_creation")),
                "metrics": creation_metrics,
                "definitions": {
                    "xa": _safe(row.get("xa_definition")),
                    "chance_creation": _safe(row.get("chance_creation_definition")),
                },
            },
        }

    @staticmethod
    def _radar_mode(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
        if mode == "biggest-risers":
            supported = frame.get(
                "_latest_development_supported", frame["development"].notna()
            )
            return frame[supported & frame["development"].gt(0)]
        if mode == "u21":
            return frame[frame["age"] <= 21]
        if mode == "underlying-output":
            supported = frame.get(
                "_latest_underlying_output_supported",
                frame["underlying_output_label"].eq("Production Lag")
                & frame["output_gap"].gt(0),
            )
            return frame[
                supported
                & frame["underlying_output_label"].eq("Production Lag")
                & frame["output_gap"].gt(0)
            ]
        if mode == "role-changes":
            supported = frame.get(
                "_latest_role_change_supported", frame["role_changed"].fillna(False)
            )
            return frame[supported]
        if mode == "creators":
            return frame[frame["primary_role"].isin(CREATOR_ROLES)]
        if mode == "scorers":
            return frame[frame["primary_role"].isin(SCORER_ROLES)]
        if mode == "midfield":
            return frame[frame["role_group"] == "Midfield"]
        if mode == "defensive":
            return frame[frame["role_group"] == "Defence"]
        return frame

    @staticmethod
    def _normalized_season_year(frame: pd.DataFrame) -> pd.Series:
        """Return the product season year, not the provider's raw season year."""

        if "candidate_window" in frame:
            season = frame["candidate_window"]
        else:
            season = pd.Series(pd.NA, index=frame.index, dtype="string")
        if "season_name" in frame:
            season = season.fillna(frame["season_name"])
        return pd.to_numeric(
            season.astype("string").str.extract(r"^(\d{4})", expand=False),
            errors="coerce",
        )

    @staticmethod
    def _radar_identity(frame: pd.DataFrame) -> pd.Series:
        if "canonical_person_id" in frame:
            identity = frame["canonical_person_id"].copy()
        else:
            identity = pd.Series(pd.NA, index=frame.index, dtype="object")
        return identity.fillna(frame["player_season_id"])

    @classmethod
    def _radar_rolling_frame(
        cls, source: pd.DataFrame
    ) -> tuple[pd.DataFrame, int | None, list[str]]:
        """Build the current-player rolling view from normalized season windows."""

        if source.empty:
            return source.copy(), None, []

        work = source.copy()
        work["_normalized_season_year"] = cls._normalized_season_year(work)
        work = work[work["_normalized_season_year"].notna()].copy()
        if work.empty:
            return work, None, []

        latest_year = int(work["_normalized_season_year"].max())
        work = work[
            work["_normalized_season_year"].between(
                latest_year - 2, latest_year, inclusive="both"
            )
        ].copy()
        work["_identity"] = cls._radar_identity(work)
        work["_confidence_sort"] = pd.to_numeric(
            work.get("confidence_score", pd.Series(index=work.index)), errors="coerce"
        )
        work["_minutes_sort"] = pd.to_numeric(
            work.get("minutes", pd.Series(index=work.index)), errors="coerce"
        )
        work["_player_season_sort"] = work["player_season_id"].astype(str)
        work = work.sort_values(
            [
                "_normalized_season_year",
                "_identity",
                "_confidence_sort",
                "_minutes_sort",
                "_player_season_sort",
            ],
            ascending=[False, True, False, False, True],
            na_position="last",
            kind="stable",
        ).drop_duplicates(["_identity", "_normalized_season_year"], keep="first")
        ranking_seasons = cls._radar_season_labels(work, latest_year)

        latest = work[work["_normalized_season_year"].eq(latest_year)].copy()
        if latest.empty:
            return latest, latest_year, ranking_seasons
        current_identities = set(latest["_identity"])
        work = work[work["_identity"].isin(current_identities)].copy()

        season_counts = work.groupby("_identity")["_normalized_season_year"].nunique()
        latest["ranking_season_count"] = latest["_identity"].map(season_counts).astype(int)

        latest["_latest_development_supported"] = latest["development"].notna()
        latest["_latest_role_change_supported"] = latest["role_changed"].fillna(False)
        latest["_latest_underlying_output_supported"] = (
            latest["underlying_output_label"].eq("Production Lag")
            & pd.to_numeric(latest["output_gap"], errors="coerce").gt(0)
        )
        # Keep the latest row as the dossier identity/context, replacing only fields whose
        # values are meaningful as cross-season current-performance evidence.
        for field in RADAR_AGGREGATE_FIELDS:
            if field not in work.columns:
                continue
            values = pd.to_numeric(work[field], errors="coerce")
            row_weights = work["_normalized_season_year"].map(
                lambda year: RADAR_RECENCY_WEIGHTS.get(latest_year - int(year), np.nan)
            )
            weighted = (values * row_weights).groupby(work["_identity"]).sum(min_count=1)
            available_weight = row_weights.where(values.notna()).groupby(
                work["_identity"]
            ).sum(min_count=1)
            aggregate = weighted.div(available_weight.replace(0, np.nan)).round(3)
            mapped = latest["_identity"].map(aggregate)
            latest[field] = mapped.where(mapped.notna(), latest[field])

        if "development" in work.columns:
            development = pd.to_numeric(work["development"], errors="coerce")
            development_weights = work["_normalized_season_year"].map(
                lambda year: RADAR_RECENCY_WEIGHTS.get(latest_year - int(year), np.nan)
                if latest_year - int(year) in (0, 1)
                else np.nan
            )
            weighted = (development * development_weights).groupby(
                work["_identity"]
            ).sum(min_count=1)
            available_weight = development_weights.where(development.notna()).groupby(
                work["_identity"]
            ).sum(min_count=1)
            aggregate = weighted.div(available_weight.replace(0, np.nan)).round(3)
            mapped = latest["_identity"].map(aggregate)
            latest["development"] = mapped.where(mapped.notna(), latest["development"])

        return (
            latest,
            latest_year,
            ranking_seasons,
        )

    @staticmethod
    def _radar_season_labels(frame: pd.DataFrame, latest_year: int) -> list[str]:
        labels: dict[int, str] = {}
        for year, group in frame.groupby("_normalized_season_year", sort=False):
            if pd.isna(year):
                continue
            candidates = group.get("candidate_window", pd.Series(dtype=object)).dropna()
            if candidates.empty:
                candidates = group.get("season_name", pd.Series(dtype=object)).dropna()
            labels[int(year)] = str(candidates.iloc[0]) if not candidates.empty else (
                f"{int(year)}/{str(int(year) + 1)[-2:]}"
            )
        return [
            labels.get(year, f"{year}/{str(year + 1)[-2:]}")
            for year in range(latest_year, latest_year - 3, -1)
        ]

    def radar(
        self,
        *,
        mode: str,
        season: str | None,
        league: str | None,
        minimum_age: float | None,
        maximum_age: float | None,
        role: str | None,
        position: str | None,
        minimum_minutes: float,
        confidence: str | None,
        sort_by: str,
        sort_order: str,
        offset: int,
        limit: int,
    ) -> tuple[pd.DataFrame, int, dict[str, Any]]:
        frame = self.intelligence_frame
        rolling = not season
        if rolling:
            frame, _latest_year, ranking_seasons = self._radar_rolling_frame(frame)
            ranking = {
                "ranking_window": "current_3_seasons",
                "ranking_seasons": ranking_seasons,
                "ranking_method": (
                    "Current identities with a latest-season representative; performance values "
                    "use normalized-season recency weights of 50% latest, 30% prior and 20% oldest, "
                    "renormalized when a field is unavailable. The returned player_season_id is "
                    "the latest dossier row."
                ),
            }
        else:
            season_match = frame["season_name"] == season
            if "candidate_window" in frame:
                season_match = season_match | (frame["candidate_window"] == season)
            frame = frame[season_match]
            if not frame.empty:
                frame = (
                    frame.assign(
                        _identity=self._radar_identity(frame),
                        _minutes_sort=pd.to_numeric(frame["minutes"], errors="coerce"),
                        _player_season_sort=frame["player_season_id"].astype(str),
                    )
                    .sort_values(
                        ["_identity", "_minutes_sort", "_player_season_sort"],
                        ascending=[True, False, True],
                        na_position="last",
                        kind="stable",
                    )
                    .drop_duplicates("_identity", keep="first")
                )
            ranking = {
                "ranking_window": "single_season",
                "ranking_seasons": [season] if season else [],
                "ranking_method": (
                    "Historical single-season player-season evidence; no rolling aggregation."
                ),
            }
        if league:
            frame = frame[frame["competition_name"] == league]
        frame = self._radar_mode(frame, mode)
        if minimum_age is not None:
            frame = frame[frame["age"] >= minimum_age]
        if maximum_age is not None:
            frame = frame[frame["age"] <= maximum_age]
        if role:
            frame = frame[frame["primary_role"] == role]
        if position:
            frame = frame[
                frame["positions"].str.contains(position, case=False, regex=False, na=False)
            ]
        if minimum_minutes:
            frame = frame[frame["minutes"] >= minimum_minutes]
        if confidence:
            frame = frame[frame["confidence_label"] == confidence]

        total = len(frame)
        ascending = sort_order == "asc"
        frame = frame.assign(_player_name=frame["player_name"].fillna("").astype(str).str.casefold())
        frame = frame.sort_values(
            [sort_by, "_player_name", "player_season_id"],
            ascending=[ascending, True, True],
            na_position="last",
            kind="stable",
        )
        return (
            frame.iloc[offset : offset + limit].drop(columns="_player_name"),
            total,
            ranking,
        )

    @staticmethod
    def _league_mode(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
        if mode == "risers":
            return ExactScoutprintService._radar_mode(frame, "biggest-risers")
        if mode == "attackers":
            return frame[frame["role_group"] == "Attack"]
        if mode == "progressors":
            return frame[frame["primary_role"].isin(PROGRESSOR_ROLES)]
        if mode == "defenders":
            return frame[frame["role_group"] == "Defence"]
        return ExactScoutprintService._radar_mode(frame, mode)

    def league_explorer(
        self,
        *,
        league: str,
        season: str,
        minimum_minutes: float,
        limit_per_mode: int,
    ) -> dict[str, Any]:
        frame = self.intelligence_frame[
            (self.intelligence_frame["competition_name"] == league)
            & (
                (self.intelligence_frame["season_name"] == season)
                | (self.intelligence_frame["candidate_window"] == season)
            )
        ]
        if minimum_minutes:
            frame = frame[frame["minutes"] >= minimum_minutes]

        role_counts = (
            frame["primary_role"]
            .fillna("Unclassified")
            .astype(str)
            .value_counts()
            .rename_axis("role")
            .reset_index(name="players")
            .sort_values(["players", "role"], ascending=[False, True], kind="stable")
        )
        population = len(frame)
        roles = [
            {
                "role": row["role"],
                "players": int(row["players"]),
                "share": round(100 * int(row["players"]) / population, 1) if population else 0.0,
            }
            for _, row in role_counts.iterrows()
        ]

        leaderboards = []
        for mode, label in LEAGUE_MODES.items():
            board = self._league_mode(frame, mode)
            sort_field = LEAGUE_DEFAULT_SORTS[mode]
            board = board.assign(
                _player_name=board["player_name"].fillna("").astype(str).str.casefold()
            ).sort_values(
                [sort_field, "_player_name", "player_season_id"],
                ascending=[False, True, True],
                na_position="last",
                kind="stable",
            )
            leaderboards.append(
                {
                    "id": mode,
                    "label": label,
                    "sort": {"field": sort_field, "order": "desc"},
                    "available": len(board),
                    "players": [
                        self.intelligence_record(row)
                        for _, row in board.head(limit_per_mode).iterrows()
                    ],
                }
            )

        return {
            "player_seasons": population,
            "players": int(frame["canonical_person_id"].nunique()),
            "clubs": int(frame["team_name"].dropna().nunique()),
            "classified_roles": int(
                (
                    frame["primary_role"].notna()
                    & ~frame["primary_role"].isin({"Unclassified", "Goalkeeper"})
                ).sum()
            )
            if population
            else 0,
            "role_distribution": roles,
            "leaderboards": leaderboards,
        }

    def team_explorer(
        self,
        *,
        team: str,
        league: str,
        season: str,
        minimum_minutes: float,
        limit: int,
    ) -> dict[str, Any]:
        frame = self.intelligence_frame[
            (self.intelligence_frame["team_name"] == team)
            & (self.intelligence_frame["competition_name"] == league)
            & (
                (self.intelligence_frame["season_name"] == season)
                | (self.intelligence_frame["candidate_window"] == season)
            )
        ]
        if minimum_minutes:
            frame = frame[frame["minutes"] >= minimum_minutes]

        def ranked_players(source: pd.DataFrame, field: str) -> list[dict[str, Any]]:
            ranked = source.assign(
                _player_name=source["player_name"].fillna("").astype(str).str.casefold()
            ).sort_values(
                [field, "minutes", "_player_name", "player_season_id"],
                ascending=[False, False, True, True],
                na_position="last",
                kind="stable",
            )
            return [
                self.intelligence_record(row)
                for _, row in ranked.head(limit).drop(columns="_player_name").iterrows()
            ]

        depth = []
        depth_frame = frame.assign(
            _role=frame["primary_role"].fillna("Unclassified").astype(str),
            _minutes=pd.to_numeric(frame["minutes"], errors="coerce").fillna(0),
            _current=pd.to_numeric(frame["current_level"], errors="coerce"),
            _player_name=frame["player_name"].fillna("").astype(str).str.casefold(),
        )
        for role, group in depth_frame.groupby("_role", sort=True):
            group = group.sort_values(
                ["_minutes", "_current", "_player_name", "player_season_id"],
                ascending=[False, False, True, True],
                na_position="last",
                kind="stable",
            )
            depth.append(
                {
                    "role": role,
                    "players": len(group),
                    "minutes": round(float(group["_minutes"].sum()), 1),
                    "options": [
                        self.intelligence_record(row)
                        for _, row in group.head(4).drop(
                            columns=["_role", "_minutes", "_current", "_player_name"]
                        ).iterrows()
                    ],
                }
            )
        depth.sort(key=lambda item: (-item["minutes"], item["role"]))

        minutes = pd.to_numeric(frame["minutes"], errors="coerce").fillna(0)
        u21_minutes = minutes[frame["age"].le(21).fillna(False)].sum()
        total_minutes = minutes.sum()
        breakouts = frame[frame["breakout_score"].notna()]
        key_players = frame[frame["current_level"].notna()]
        return {
            "player_seasons": len(frame),
            "players": int(frame["canonical_person_id"].nunique()),
            "classified_roles": int(
                (
                    frame["primary_role"].notna()
                    & ~frame["primary_role"].isin({"Unclassified", "Goalkeeper"})
                ).sum()
            ),
            "spatial_players": int(frame["spatial_available"].fillna(False).sum()),
            "u21_minutes": round(float(u21_minutes), 1),
            "u21_minutes_share": (
                round(100 * float(u21_minutes) / float(total_minutes), 1)
                if total_minutes
                else None
            ),
            "key_players": ranked_players(key_players, "current_level"),
            "breakouts": ranked_players(breakouts, "breakout_score"),
            "role_depth": depth,
        }

    def player_explorer(
        self,
        *,
        player: str | None,
        club: str | None,
        league: str | None,
        season: str | None,
        minimum_age: float | None,
        maximum_age: float | None,
        role: str | None,
        position: str | None,
        minimum_minutes: float,
        data_tier: str | None,
        confidence: str | None,
        sort_by: str,
        sort_order: str,
        unique_players: bool,
        offset: int,
        limit: int,
    ) -> tuple[pd.DataFrame, int, int]:
        frame = self.intelligence_frame
        if player:
            frame = frame[
                frame["player_name"].str.contains(player, case=False, regex=False, na=False)
            ]
        if club:
            frame = frame[
                frame["team_name"].str.contains(club, case=False, regex=False, na=False)
            ]
        if league:
            frame = frame[frame["competition_name"] == league]
        if season:
            frame = frame[
                (frame["season_name"] == season) | (frame["candidate_window"] == season)
            ]
        if minimum_age is not None:
            frame = frame[frame["age"] >= minimum_age]
        if maximum_age is not None:
            frame = frame[frame["age"] <= maximum_age]
        if role:
            frame = frame[frame["primary_role"] == role]
        if position:
            frame = frame[
                frame["positions"].str.contains(position, case=False, regex=False, na=False)
            ]
        if minimum_minutes:
            frame = frame[frame["minutes"] >= minimum_minutes]
        if data_tier:
            frame = frame[frame["data_tier"] == data_tier]
        if confidence:
            frame = frame[frame["confidence_label"] == confidence]

        player_seasons = len(frame)
        if unique_players and not frame.empty:
            identity = frame["canonical_person_id"].fillna(frame["player_season_id"])
            season_key = pd.to_numeric(
                frame["candidate_window"].fillna(frame["season_name"]).str.extract(
                    r"(\d{4})", expand=False
                ),
                errors="coerce",
            )
            frame = (
                frame.assign(_identity=identity, _season_key=season_key)
                .sort_values(
                    ["_season_key", "minutes", "radar_score", "player_season_id"],
                    ascending=[False, False, False, True],
                    na_position="last",
                    kind="stable",
                )
                .drop_duplicates("_identity", keep="first")
                .drop(columns=["_identity", "_season_key"])
            )

        total = len(frame)
        ascending = sort_order == "asc"
        column = PLAYER_SORT_FIELDS[sort_by]
        frame = frame.assign(_player_name=frame["player_name"].fillna("").astype(str).str.casefold())
        frame = frame.sort_values(
            [column, "_player_name", "player_season_id"],
            ascending=[ascending, True, True],
            na_position="last",
            kind="stable",
        )
        return (
            frame.iloc[offset : offset + limit].drop(columns="_player_name"),
            total,
            player_seasons,
        )

    def player_explorer_record(self, row: pd.Series) -> dict[str, Any]:
        record = self.intelligence_record(row)
        person_id = row.get("canonical_person_id")
        profiles = self.frame[self.frame["canonical_person_id"] == person_id]
        names = sorted(
            set(profiles["player_name"].dropna().astype(str)),
            key=lambda value: ("\\u" in value, len(value.split()), len(value), value),
        )
        profile_rows = profiles.sort_values(
            ["season_start_year", "competition_name"], ascending=[False, True]
        )
        record.update(
            {
                "player_name": names[0] if names else record["player_name"],
                "clubs": sorted(set(profiles["team_name"].dropna().astype(str))),
                "competitions": sorted(
                    set(profiles["competition_name"].dropna().astype(str))
                ),
                "season_count": int(profiles["season_name"].nunique()),
                "profile_count": len(profiles),
                "profiles": [
                    {
                        **{field: _safe(profile.get(field)) for field in PROFILE_FIELDS},
                        "canonical_player_id": person_id,
                    }
                    for _, profile in profile_rows.iterrows()
                ],
            }
        )
        return record

    def role_search(
        self,
        *,
        role: str,
        leagues: list[str],
        season: str | None,
        minimum_age: float | None,
        maximum_age: float | None,
        minimum_minutes: float,
        sort_by: str,
        sort_order: str,
        offset: int,
        limit: int,
    ) -> tuple[pd.DataFrame, int, int]:
        frame = self.intelligence_frame[self.intelligence_frame["primary_role"] == role]
        if leagues:
            frame = frame[frame["competition_name"].isin(leagues)]
        if season:
            frame = frame[
                (frame["season_name"] == season) | (frame["candidate_window"] == season)
            ]
        if minimum_age is not None:
            frame = frame[frame["age"] >= minimum_age]
        if maximum_age is not None:
            frame = frame[frame["age"] <= maximum_age]
        if minimum_minutes:
            frame = frame[frame["minutes"] >= minimum_minutes]

        player_seasons = len(frame)
        if not frame.empty:
            identity = frame["canonical_person_id"].fillna(frame["player_season_id"])
            season_key = pd.to_numeric(
                frame["candidate_window"].fillna(frame["season_name"]).str.extract(
                    r"(\d{4})", expand=False
                ),
                errors="coerce",
            )
            frame = (
                frame.assign(_identity=identity, _season_key=season_key)
                .sort_values(
                    ["_season_key", "minutes", "current_level", "player_season_id"],
                    ascending=[False, False, False, True],
                    na_position="last",
                    kind="stable",
                )
                .drop_duplicates("_identity", keep="first")
                .drop(columns=["_identity", "_season_key"])
            )

        total = len(frame)
        column = RECRUITMENT_SORT_FIELDS[sort_by]
        ascending = sort_order == "asc"
        frame = frame.assign(_player_name=frame["player_name"].fillna("").astype(str).str.casefold())
        frame = frame.sort_values(
            [column, "_player_name", "player_season_id"],
            ascending=[ascending, True, True],
            na_position="last",
            kind="stable",
        )
        return (
            frame.iloc[offset : offset + limit].drop(columns="_player_name"),
            total,
            player_seasons,
        )

    def role_search_record(self, row: pd.Series) -> dict[str, Any]:
        record = self.intelligence_record(row)
        evidence = record.get("role_evidence") or {}
        dimensions = evidence.get("dimensions") if isinstance(evidence, dict) else []
        record["role_fit"] = _safe(row.get("role_confidence_score"))
        record["role_fit_evidence"] = {
            "metric_coverage": _safe(row.get("metric_coverage")),
            "dimensions": dimensions if isinstance(dimensions, list) else [],
            "position_support": evidence.get("position_support")
            if isinstance(evidence, dict)
            else None,
        }
        return record

    @staticmethod
    def _normalized_name(value: Any) -> str:
        text = re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda match: chr(int(match.group(1), 16)),
            str(value or ""),
        )
        text = unicodedata.normalize("NFKD", text)
        text = "".join(character for character in text if not unicodedata.combining(character))
        return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))

    @classmethod
    def _names_compatible(cls, left: Any, right: Any) -> bool:
        left_tokens = cls._normalized_name(left).split()
        right_tokens = cls._normalized_name(right).split()
        if not left_tokens or not right_tokens or left_tokens[0] != right_tokens[0]:
            return False
        if left_tokens == right_tokens:
            return True
        shorter, longer = sorted((left_tokens, right_tokens), key=len)
        return len(shorter) >= 2 and all(token in longer for token in shorter)

    @classmethod
    def _normalized_team(cls, value: Any) -> str:
        ignored = {"fc", "cf", "sc", "club", "football"}
        return " ".join(
            token
            for token in cls._normalized_name(value).split()
            if token not in ignored and not token.isdigit()
        )

    @classmethod
    def _canonical_person_ids(cls, frame: pd.DataFrame) -> pd.Series:
        """Reconcile canonical aliases using existing identity evidence only.

        This closes conservative cross-provider gaps such as full-name versus abbreviated-name
        records. A merge requires either the same DOB plus compatible names, or compatible
        first/surname evidence plus an overlapping normalized team-season.
        """

        canonical_ids = sorted(frame["canonical_player_id"].dropna().astype(str).unique())
        parent = {value: value for value in canonical_ids}

        def find(value: str) -> str:
            while parent[value] != value:
                parent[value] = parent[parent[value]]
                value = parent[value]
            return value

        def union(left: str, right: str) -> None:
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parent[max(left_root, right_root)] = min(left_root, right_root)

        evidence: dict[str, dict[str, set[str]]] = {}
        evidence_columns = [
            "canonical_player_id",
            "player_name",
            "canonical_birth_date",
            "birth_date",
            "canonical_nationality",
            "nationality",
            "team_name",
            "season_start_year",
        ]
        for row in frame[evidence_columns].itertuples(index=False):
            if pd.isna(row.canonical_player_id):
                continue
            item = evidence.setdefault(
                str(row.canonical_player_id),
                {
                    "names": set(),
                    "raw_names": set(),
                    "dobs": set(),
                    "nationalities": set(),
                    "team_seasons": set(),
                },
            )
            if pd.notna(row.player_name):
                item["names"].add(cls._normalized_name(row.player_name))
                item["raw_names"].add(str(row.player_name))
            for value in (row.canonical_birth_date, row.birth_date):
                if pd.notna(value):
                    item["dobs"].add(str(value))
            for value in (row.canonical_nationality, row.nationality):
                if pd.notna(value):
                    item["nationalities"].add(cls._normalized_name(value))
            if pd.notna(row.team_name) and pd.notna(row.season_start_year):
                item["team_seasons"].add(
                    f"{cls._normalized_team(row.team_name)}:{row.season_start_year}"
                )
        by_dob: dict[str, set[str]] = {}
        by_name_anchor: dict[tuple[str, str], set[str]] = {}
        for canonical_id, item in evidence.items():
            for dob in item["dobs"]:
                by_dob.setdefault(dob, set()).add(canonical_id)
            for normalized_name in item["names"]:
                tokens = normalized_name.split()
                if len(tokens) >= 2:
                    by_name_anchor.setdefault((tokens[0], tokens[-1]), set()).add(
                        canonical_id
                    )

        for group in by_dob.values():
            ordered = sorted(group)
            for index, left in enumerate(ordered):
                for right in ordered[index + 1 :]:
                    if any(
                        cls._names_compatible(left_name, right_name)
                        for left_name in evidence[left]["raw_names"]
                        for right_name in evidence[right]["raw_names"]
                    ):
                        union(left, right)

        for group in by_name_anchor.values():
            ordered = sorted(group)
            for index, left in enumerate(ordered):
                a = evidence[left]
                for right in ordered[index + 1 :]:
                    b = evidence[right]
                    names_compatible = any(
                        cls._names_compatible(left_name, right_name)
                        for left_name in a["raw_names"]
                        for right_name in b["raw_names"]
                    )
                    shared_team_season = bool(
                        a["team_seasons"].intersection(b["team_seasons"])
                    )
                    if names_compatible and shared_team_season:
                        union(left, right)
        return frame["canonical_player_id"].map(
            lambda value: find(str(value)) if pd.notna(value) else None
        )

    @staticmethod
    def _candidate_window(row: pd.Series) -> str | None:
        year = row.get("season_start_year")
        if pd.isna(year):
            return None
        year = int(year)
        if row.get("source_provider") == "american_soccer_analysis":
            return f"{year - 1}/{str(year)[-2:]}"
        return f"{year}/{str(year + 1)[-2:]}"

    @property
    def recent_frame(self) -> pd.DataFrame:
        return self.frame[self.frame["candidate_window"].isin({"2023/24", "2024/25", "2025/26"})]

    def _reference(self, request: SimilarSearchRequest) -> pd.Series:
        try:
            reference = self.by_id.loc[request.reference_player_season_id]
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Reference player-season not found") from error
        if isinstance(reference, pd.DataFrame):
            reference = reference.iloc[0]
        if (
            request.reference_competition
            and reference["competition_name"] != request.reference_competition
        ):
            raise HTTPException(status_code=422, detail="Reference competition does not match ID")
        if request.reference_season and reference["season_name"] != request.reference_season:
            raise HTTPException(status_code=422, detail="Reference season does not match ID")
        return reference

    def candidate_frame(self, request: SimilarSearchRequest) -> tuple[pd.DataFrame, pd.Series]:
        reference = self._reference(request)
        candidates = self.recent_frame if request.recent_candidates_only else self.frame
        reference_person_id = reference.get("canonical_person_id")
        if pd.notna(reference_person_id):
            candidates = candidates[candidates["canonical_person_id"] != reference_person_id]
        if request.candidate_competitions:
            candidates = candidates[
                candidates["competition_name"].isin(request.candidate_competitions)
            ]
        if request.candidate_seasons:
            candidates = candidates[candidates["season_name"].isin(request.candidate_seasons)]
        if request.candidate_windows:
            candidates = candidates[candidates["candidate_window"].isin(request.candidate_windows)]
        if request.candidate_positions:
            pattern = "|".join(re.escape(position) for position in request.candidate_positions)
            candidates = candidates[
                candidates["positions"].str.contains(pattern, case=False, regex=True, na=False)
            ]
        if request.data_tiers:
            candidates = candidates[candidates["data_tier"].isin(request.data_tiers)]
        candidates = candidates[candidates["minutes"].fillna(-1) >= request.minimum_minutes]
        if request.minimum_age is not None:
            candidates = candidates[candidates["age"].notna()]
            candidates = candidates[candidates["age"] >= request.minimum_age]
        if request.maximum_age is not None:
            candidates = candidates[candidates["age"].notna()]
            candidates = candidates[candidates["age"] <= request.maximum_age]
        reference_frame = self.by_id.loc[[request.reference_player_season_id]].reset_index(drop=True)
        role_pool = (
            pd.concat([candidates, reference_frame], ignore_index=True)
            .drop_duplicates("player_season_id")
            .reset_index(drop=True)
        )
        role_pool, reference_roles = add_role_compatibility(
            role_pool, request.reference_player_season_id
        )
        role_pool["Reference role families"] = [reference_roles] * len(role_pool)
        compatible = role_pool[
            (role_pool["player_season_id"] == request.reference_player_season_id)
            | (role_pool["Role compatibility"] >= request.minimum_role_compatibility)
        ]
        return compatible.reset_index(drop=True), reference

    @staticmethod
    def _add_recommendation_evidence(ranked: pd.DataFrame) -> pd.DataFrame:
        output = ranked.copy()
        category_columns = ["Spatial role", *CATEGORY_METRICS]
        meaningful = output[category_columns].notna().sum(axis=1)
        coverage = output["Comparable profile coverage"].fillna(0).clip(0, 100) / 100
        dimension_reliability = (meaningful / len(category_columns)).clip(0, 1)
        minute_reliability = np.sqrt(output["minutes"].fillna(0).clip(lower=0) / 1800).clip(0, 1)
        tier_reliability = output["data_tier"].map({"A": 1.0, "B": 0.92, "C": 0.86}).fillna(0.82)
        evidence = (
            0.6 * coverage
            + 0.2 * dimension_reliability
            + 0.15 * minute_reliability
            + 0.05 * tier_reliability
        )
        output["Meaningful dimensions"] = meaningful
        output["Evidence quality"] = 100 * evidence
        output["Confidence factor"] = 0.55 + 0.45 * evidence
        role_quality = output["Role compatibility"].fillna(0).clip(0, 100) / 100
        output["Role recommendation factor"] = 0.35 + 0.65 * role_quality
        output["Recommendation"] = (
            output["Overall"]
            * output["Confidence factor"]
            * output["Role recommendation factor"]
        )
        output["Confidence label"] = np.select(
            [evidence >= 0.8, evidence >= 0.62], ["HIGH", "MEDIUM"], default="LOW"
        )
        return output

    @staticmethod
    def _collapse_unique_players(ranked: pd.DataFrame) -> pd.DataFrame:
        if ranked.empty:
            return ranked
        identity = ranked.get(
            "canonical_person_id", ranked["canonical_player_id"]
        ).fillna(ranked["canonical_player_id"])
        ranked = ranked.assign(_identity=identity)
        return (
            ranked.sort_values(
                ["Recommendation", "Overall", "Comparable profile coverage", "minutes"],
                ascending=[False, False, False, False],
            )
            .drop_duplicates("_identity", keep="first")
            .drop(columns="_identity")
        )

    def run_search(self, request: SimilarSearchRequest) -> tuple[pd.DataFrame, float]:
        candidates, _reference = self.candidate_frame(request)
        started = time.perf_counter()
        ranked = rank_similar(
            candidates,
            request.reference_player_season_id,
            request.weights,
            min_minutes=request.minimum_minutes,
            mirror_mode=request.mirror_mode,
            max_spatial_candidates=request.exact_shortlist_size,
        )
        ranked = ranked[
            ranked["Comparable profile coverage"] >= request.minimum_comparison_coverage
        ]
        ranked = ranked[ranked["Overall"] >= request.minimum_profile_match]
        ranked = self._add_recommendation_evidence(ranked)
        if not request.include_low_confidence:
            ranked = ranked[ranked["Confidence label"] != "LOW"]
        if request.unique_players:
            ranked = self._collapse_unique_players(ranked)
        ranked = ranked.sort_values(
            ["Recommendation", "Overall", "Comparable profile coverage"],
            ascending=[False, False, False],
        ).reset_index(drop=True)
        return ranked, (time.perf_counter() - started) * 1000

    def result(self, row: pd.Series, rank: int) -> dict[str, Any]:
        categories = {
            category: _safe(row.get(category))
            for category in ["Spatial role", *CATEGORY_METRICS]
            if _safe(row.get(category)) is not None
        }
        missing = str(row.get("Unavailable dimensions") or "None")
        ordered_categories = sorted(
            categories.items(), key=lambda item: item[1], reverse=True
        )
        top_matches = [
            {"dimension": category, "score": round(float(score), 1)}
            for category, score in ordered_categories[:3]
        ]
        biggest_differences = [
            {"dimension": category, "score": round(float(score), 1)}
            for category, score in sorted(categories.items(), key=lambda item: item[1])[:2]
        ]
        person_id = _safe(row.get("canonical_person_id"))
        return {
            "rank": rank,
            "player_season_id": row["player_season_id"],
            "canonical_player_id": person_id or row.get("canonical_player_id"),
            "player_name": row["player_name"],
            "club": row.get("team_name"),
            "competition": row.get("competition_name"),
            "season": row.get("season_name"),
            "position": row.get("positions"),
            "source_provider": row.get("source_provider"),
            "data_tier": row.get("data_tier") or "C",
            "age": _safe(row.get("age")),
            "minutes": _safe(row.get("minutes")),
            "profile_match": _safe(row.get("Overall")),
            "recommendation_score": _safe(row.get("Recommendation")),
            "confidence_factor": _safe(row.get("Confidence factor")),
            "role_recommendation_factor": _safe(row.get("Role recommendation factor")),
            "confidence": row.get("Confidence label"),
            "meaningful_dimensions": _safe(row.get("Meaningful dimensions")),
            "spatial_match": _safe(row.get("Spatial role")),
            "same_side_match": _safe(row.get("Same-side")),
            "mirrored_match": _safe(row.get("Mirrored")),
            "category_similarities": categories,
            "comparison_coverage": _safe(row.get("Comparable profile coverage")),
            "role_compatibility": _safe(row.get("Role compatibility")),
            "role_family": row.get("Role family"),
            "reference_role_families": row.get("Reference role families") or {},
            "top_matching_dimensions": top_matches,
            "biggest_differences": biggest_differences,
            "xg": _safe(row.get("xg")),
            "xa": _safe(row.get("xa")),
            "xg_p90": _safe(row.get("xg_p90")),
            "xa_p90": _safe(row.get("xa_p90")),
            "goals_p90": _safe(row.get("goals_p90")),
            "assists_p90": _safe(row.get("assists_p90")),
            "shots_p90": _safe(row.get("shots_p90")),
            "candidate_window": row.get("candidate_window"),
            "unavailable_categories": [] if missing == "None" else missing.split(", "),
        }

    def compact_profile(self, row: pd.Series) -> dict[str, Any]:
        maps = {name: _safe(row.get(column)) for name, column in MAP_FIELDS.items()}
        stats = {field: _safe(row.get(field)) for field in STAT_FIELDS}
        available = {
            field.removesuffix("_available"): bool(_safe(row.get(field)) or False)
            for field in AVAILABILITY_FIELDS
        }
        profile = {
            **{field: _safe(row.get(field)) for field in PROFILE_FIELDS},
            "grid": [
                int(row["grid_x"]) if pd.notna(row.get("grid_x")) else 12,
                int(row["grid_y"]) if pd.notna(row.get("grid_y")) else 8,
            ],
            "maps": maps,
            "statistics": stats,
            "availability": available,
            "definitions": {
                "xg": _safe(row.get("xg_definition")),
                "xa": _safe(row.get("xa_definition")),
                "carry": _safe(row.get("carry_definition")),
                "chance_creation": _safe(row.get("chance_creation_definition")),
                "progression": _safe(row.get("progression_definition")),
                "dribble": _safe(row.get("dribble_definition")),
            },
        }
        profile["canonical_player_id"] = _safe(row.get("canonical_person_id")) or profile.get(
            "canonical_player_id"
        )
        return profile

    def profile_by_id(self, player_season_id: str) -> dict[str, Any]:
        try:
            row = self.by_id.loc[player_season_id]
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Player-season not found") from error
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        return self.compact_profile(row)


class PitchApiMatchService:
    """Read an explicit, safe projection of completed PitchAPI cache files."""

    ENDPOINTS = ("lineups", "shots", "players", "advanced_players", "network")
    PLAYER_STATS: ClassVar[dict[str, str]] = {
        "rating_title": "rating",
        "minutes_played": "minutes",
        "goals": "goals",
        "assists": "assists",
        "xg_and_xa": "xg_xa",
        "expected_assists": "xa",
        "accurate_passes": "accurate_passes",
        "chances_created": "chances_created",
        "touches": "touches",
        "touches_opp_box": "box_touches",
        "defensive_actions": "defensive_actions",
    }

    def __init__(self, cache_root: Path):
        self.cache_root = cache_root
        self.match_root = cache_root / "match_data"
        self._reload_lock = threading.RLock()
        self._batch_marker_path = cache_root.parents[2] / "private/state/pitchapi_queue_summary.json"
        self._batch_generation = self._path_signature(self._batch_marker_path)
        self.matches = self._load_matches()

    @staticmethod
    def _path_signature(path: Path) -> tuple[int, int] | None:
        if not path.exists():
            return None
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns

    def _load_matches(self) -> dict[str, dict[str, Any]]:
        matches: dict[str, dict[str, Any]] = {}
        if not self.match_root.exists():
            raise FileNotFoundError(f"PitchAPI match cache not found: {self.match_root}")
        for path in sorted(self.match_root.glob("match=*/match.json")):
            try:
                payload = json.loads(path.read_text())
                raw = payload.get("data") or {}
                match_id = str(raw.get("id") or path.parent.name.removeprefix("match="))
                if not match_id or not isinstance(raw, dict):
                    continue
                matches[match_id] = self._match_record(raw, path.parent)
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
        if not matches:
            raise ValueError("PitchAPI match cache contains no readable matches")
        return matches

    def reload_if_refreshed(self) -> bool:
        """Atomically rescan completed immutable caches after a collector batch."""

        generation = self._path_signature(self._batch_marker_path)
        if generation is None or generation == self._batch_generation:
            return False
        with self._reload_lock:
            generation = self._path_signature(self._batch_marker_path)
            if generation is None or generation == self._batch_generation:
                return False
            try:
                matches = self._load_matches()
            except (FileNotFoundError, OSError, ValueError):
                return False
            self.matches = matches
            self._batch_generation = generation
            return True

    @staticmethod
    def _entity(raw: Any) -> dict[str, Any]:
        raw = raw if isinstance(raw, dict) else {}
        return {"id": raw.get("id"), "name": raw.get("name")}

    @classmethod
    def _match_record(cls, raw: dict[str, Any], directory: Path) -> dict[str, Any]:
        availability = {
            endpoint: (directory / f"{endpoint}.json").exists()
            for endpoint in cls.ENDPOINTS
        }
        return {
            "id": str(raw.get("id") or ""),
            "league": cls._entity(raw.get("league")),
            "season": raw.get("season"),
            "home_team": cls._entity(raw.get("home_team")),
            "away_team": cls._entity(raw.get("away_team")),
            "date": raw.get("date"),
            "time_utc": raw.get("time_utc"),
            "status": raw.get("status"),
            "score_home": _safe(raw.get("score_home")),
            "score_away": _safe(raw.get("score_away")),
            "round": raw.get("round_name"),
            "stadium": raw.get("stadium"),
            "referee": raw.get("referee"),
            "availability": availability,
        }

    def _read(self, match_id: str, endpoint: str) -> Any:
        if match_id not in self.matches:
            raise HTTPException(status_code=404, detail="Supported match not found")
        path = self.match_root / f"match={match_id}" / f"{endpoint}.json"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=503, detail="Match evidence is unreadable") from error
        return payload.get("data") if isinstance(payload, dict) else None

    @staticmethod
    def _team_name(match: dict[str, Any], team_id: Any) -> str | None:
        for key in ("home_team", "away_team"):
            if str(match[key].get("id")) == str(team_id):
                return match[key].get("name")
        return None

    def browse(
        self,
        *,
        league: str | None,
        team: str | None,
        date_from: date | None,
        date_to: date | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = list(self.matches.values())
        if league:
            rows = [row for row in rows if row["league"].get("name") == league]
        if team:
            needle = team.casefold()
            rows = [
                row
                for row in rows
                if needle in str(row["home_team"].get("name") or "").casefold()
                or needle in str(row["away_team"].get("name") or "").casefold()
            ]
        if date_from:
            rows = [row for row in rows if str(row.get("date") or "") >= date_from.isoformat()]
        if date_to:
            rows = [row for row in rows if str(row.get("date") or "") <= date_to.isoformat()]
        rows.sort(key=lambda row: (str(row.get("date") or ""), row["id"]), reverse=True)
        return rows[offset : offset + limit], len(rows)

    @staticmethod
    def _lineup_side(raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None

        def players(key: str) -> list[dict[str, Any]]:
            return [
                {
                    "id": item.get("player_id"),
                    "name": item.get("name"),
                    "shirt_number": item.get("shirt_number"),
                    "position_id": item.get("position_id"),
                    "captain": bool(item.get("is_captain")),
                    "pitch_x": _safe(item.get("pitch_x")),
                    "pitch_y": _safe(item.get("pitch_y")),
                }
                for item in raw.get(key) or []
                if isinstance(item, dict)
            ]

        coach = raw.get("coach") if isinstance(raw.get("coach"), dict) else {}
        return {
            "formation": raw.get("formation"),
            "coach": coach.get("name"),
            "starters": players("starters"),
            "substitutes": players("subs"),
        }

    @classmethod
    def _player_rows(cls, raw: Any, match: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for item in raw if isinstance(raw, list) else []:
            player = item.get("player") if isinstance(item.get("player"), dict) else {}
            stats: dict[str, Any] = {}
            for group in item.get("stats") or []:
                for value in (group.get("stats") or {}).values():
                    key = value.get("key")
                    if key not in cls.PLAYER_STATS:
                        continue
                    stat = value.get("stat") or {}
                    projected = _safe(stat.get("value"))
                    if key == "accurate_passes" and stat.get("total") is not None:
                        projected = {"complete": projected, "attempted": _safe(stat.get("total"))}
                    stats[cls.PLAYER_STATS[key]] = projected
            rows.append(
                {
                    "id": player.get("id"),
                    "name": player.get("name"),
                    "team_id": item.get("team_id"),
                    "team": cls._team_name(match, item.get("team_id")),
                    "stats": stats,
                }
            )
        rows.sort(
            key=lambda row: (
                -(float(row["stats"].get("rating") or -1)),
                str(row.get("name") or "").casefold(),
            )
        )
        return rows

    @classmethod
    def _shots(cls, raw: Any, match: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        periods = raw.get("periods") if isinstance(raw, dict) else []
        for period in periods or []:
            for item in period.get("shots") or []:
                player = item.get("player") if isinstance(item.get("player"), dict) else {}
                rows.append(
                    {
                        "id": item.get("id"),
                        "period": period.get("period"),
                        "minute": _safe(item.get("minute")),
                        "player": cls._entity(player),
                        "team_id": item.get("team_id"),
                        "team": cls._team_name(match, item.get("team_id")),
                        "x": _safe(item.get("x")),
                        "y": _safe(item.get("y")),
                        "xg": _safe(item.get("expected_goals")),
                        "xgot": _safe(item.get("expected_goals_on_target")),
                        "on_target": bool(item.get("is_on_target")),
                        "inside_box": bool(item.get("is_inside_box")),
                        "body_part": item.get("shot_type"),
                        "situation": item.get("situation"),
                        "outcome": item.get("event_type"),
                    }
                )
        rows.sort(key=lambda row: (row.get("minute") or 0, str(row.get("id") or "")))
        return rows

    @classmethod
    def _networks(cls, raw: Any) -> list[dict[str, Any]]:
        networks = raw.get("networks") if isinstance(raw, dict) else []
        return [
            {
                "team": cls._entity(item.get("team")),
                "window": {
                    "kind": (item.get("window") or {}).get("kind"),
                    "until_seconds": _safe((item.get("window") or {}).get("until_seconds")),
                },
                "centralization": _safe(item.get("centralization")),
                "nodes": [
                    {
                        "player": cls._entity(node.get("player")),
                        "x": _safe(node.get("avg_x")),
                        "y": _safe(node.get("avg_y")),
                        "passes": _safe(node.get("passes")),
                        "received": _safe(node.get("passes_received")),
                        "connections": _safe(node.get("degree")),
                    }
                    for node in item.get("nodes") or []
                    if isinstance(node, dict)
                ],
            }
            for item in networks or []
            if isinstance(item, dict)
        ]

    @classmethod
    def _advanced(cls, raw: Any, match: dict[str, Any]) -> list[dict[str, Any]]:
        players = raw.get("players") if isinstance(raw, dict) else []
        rows = []
        for item in players or []:
            player = item.get("player") if isinstance(item.get("player"), dict) else {}
            passing, carrying = item.get("passing") or {}, item.get("carrying") or {}
            creation, defending = item.get("creation") or {}, item.get("defending") or {}
            possession = item.get("possession_value") or {}
            rows.append(
                {
                    "player": cls._entity(player),
                    "team": cls._team_name(match, item.get("team_id")),
                    "minutes": _safe(item.get("minutes_played")),
                    "actions": _safe(item.get("actions")),
                    "xt": _safe(possession.get("xt_total")),
                    "vaep": _safe(possession.get("vaep_total")),
                    "passes": _safe(passing.get("passes")),
                    "progressive_passes": _safe(passing.get("progressive_passes")),
                    "key_passes": _safe(passing.get("key_passes")),
                    "progressive_carries": _safe(carrying.get("progressive_carries")),
                    "chances_created": _safe(creation.get("chances_created")),
                    "xg_chain": _safe(creation.get("xg_chain")),
                    "tackles": _safe(defending.get("tackles")),
                    "interceptions": _safe(defending.get("interceptions")),
                }
            )
        return rows

    def detail(self, match_id: str) -> dict[str, Any]:
        if match_id not in self.matches:
            raise HTTPException(status_code=404, detail="Supported match not found")
        match = self.matches[match_id]
        lineups = self._read(match_id, "lineups")
        shots = self._shots(self._read(match_id, "shots"), match)
        players = self._player_rows(self._read(match_id, "players"), match)
        advanced = self._advanced(self._read(match_id, "advanced_players"), match)
        networks = self._networks(self._read(match_id, "network"))
        team_summary = []
        for team_key in ("home_team", "away_team"):
            team = match[team_key]
            team_shots = [shot for shot in shots if shot["team_id"] == team.get("id")]
            team_summary.append(
                {
                    "team": team,
                    "shots": len(team_shots),
                    "on_target": sum(shot["on_target"] for shot in team_shots),
                    "xg": round(sum(float(shot["xg"] or 0) for shot in team_shots), 3),
                    "big_chances": sum(float(shot["xg"] or 0) >= 0.25 for shot in team_shots),
                }
            )
        return {
            "engine": "SCOUTPRINT MATCH EVIDENCE",
            "match": match,
            "lineups": {
                "home": self._lineup_side((lineups or {}).get("home")),
                "away": self._lineup_side((lineups or {}).get("away")),
            },
            "shot_summary": team_summary,
            "shots": shots,
            "top_performers": players[:8],
            "player_stats": players,
            "advanced_players": advanced,
            "pass_networks": networks,
            "limitations": [
                "Shot maps show recorded events, not continuous tracking.",
                "Pass-network positions describe the provider window and do not prove tactics.",
                "No generated match report or unsupported causal conclusion is added.",
            ],
        }


@lru_cache(maxsize=1)
def _get_service() -> ExactScoutprintService:
    history_path = Path(
        os.getenv(
            "FOOTBALL_SCOUT_HISTORY",
            "data/private/canonical_identity/player_season_history.parquet",
        )
    )
    intelligence_path = Path(
        os.getenv(
            "FOOTBALL_SCOUT_INTELLIGENCE",
            "data/private/product/player_intelligence.parquet",
        )
    )
    return ExactScoutprintService(history_path, intelligence_path)


def get_service() -> ExactScoutprintService:
    service = _get_service()
    service.reload_if_refreshed()
    return service


@lru_cache(maxsize=1)
def _get_match_service() -> PitchApiMatchService:
    cache_root = Path(
        os.getenv("FOOTBALL_SCOUT_PITCHAPI_CACHE", "data/private/raw/pitchapi")
    )
    return PitchApiMatchService(cache_root)


def get_match_service() -> PitchApiMatchService:
    service = _get_match_service()
    service.reload_if_refreshed()
    return service


def require_api_key(
    x_scoutprint_api_key: Annotated[str | None, Header()] = None,
) -> None:
    expected = os.getenv("SCOUTPRINT_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    if not x_scoutprint_api_key or not hmac.compare_digest(x_scoutprint_api_key, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


Protected = Annotated[None, Depends(require_api_key)]
app = FastAPI(
    title="Scoutprint Private API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "scoutprint-exact-api"}


@app.get("/competitions")
def competitions(_auth: Protected) -> dict[str, Any]:
    frame = get_service().frame
    grouped = (
        frame.groupby("competition_name", dropna=False)
        .agg(player_seasons=("player_season_id", "count"), seasons=("season_name", "nunique"))
        .reset_index()
        .sort_values("competition_name")
    )
    return {
        "engine": "EXACT SCOUTPRINT",
        "competitions": [
            {
                "name": row["competition_name"],
                "player_seasons": int(row["player_seasons"]),
                "season_count": int(row["seasons"]),
            }
            for _, row in grouped.iterrows()
        ],
    }


@app.get("/seasons")
def seasons(
    _auth: Protected,
    competition: str | None = None,
) -> dict[str, Any]:
    frame = get_service().frame
    if competition:
        frame = frame[frame["competition_name"] == competition]
    grouped = (
        frame.groupby(["competition_name", "season_name"], dropna=False)
        .size()
        .reset_index(name="player_seasons")
        .sort_values(["competition_name", "season_name"], ascending=[True, False])
    )
    return {
        "seasons": [
            {
                "competition": row["competition_name"],
                "season": row["season_name"],
                "player_seasons": int(row["player_seasons"]),
            }
            for _, row in grouped.iterrows()
        ]
    }


@app.get("/recent/catalogue")
def recent_catalogue(_auth: Protected) -> dict[str, Any]:
    frame = get_service().recent_frame
    windows = (
        frame.groupby("candidate_window", dropna=False)
        .agg(
            player_seasons=("player_season_id", "count"),
            players=("canonical_player_id", "nunique"),
        )
        .reset_index()
        .sort_values("candidate_window")
    )
    competitions = (
        frame.groupby("competition_name", dropna=False)
        .size()
        .reset_index(name="player_seasons")
        .sort_values("competition_name")
    )
    tiers = frame.groupby("data_tier", dropna=False).size().to_dict()
    positions = sorted(
        {
            token.strip()
            for value in frame["positions"].dropna().astype(str)
            for token in re.split(r"[|,/;]", value)
            if token.strip()
        }
    )
    return {
        "recent_players": int(frame["canonical_player_id"].nunique()),
        "recent_player_seasons": len(frame),
        "windows": [
            {
                "window": row["candidate_window"],
                "player_seasons": int(row["player_seasons"]),
                "players": int(row["players"]),
            }
            for _, row in windows.iterrows()
        ],
        "competitions": [
            {"name": row["competition_name"], "player_seasons": int(row["player_seasons"])}
            for _, row in competitions.iterrows()
        ],
        "positions": positions,
        "tiers": {str(key): int(value) for key, value in tiers.items() if pd.notna(key)},
    }


@app.get("/intelligence/catalogue")
def intelligence_catalogue(_auth: Protected) -> dict[str, Any]:
    frame = get_service().intelligence_frame
    role_counts = frame["primary_role"].value_counts(dropna=False).sort_index()
    positions = sorted(
        {
            token.strip()
            for value in frame["positions"].dropna().astype(str)
            for token in re.split(r"[|,/;]", value)
            if token.strip()
        }
    )
    return {
        "player_seasons": len(frame),
        "players": int(frame["canonical_person_id"].nunique()),
        "development_available": int(frame["development"].notna().sum()),
        "spatial_change_available": int(frame["spatial_change"].notna().sum()),
        "roles": {
            str(role): int(count)
            for role, count in role_counts.items()
            if pd.notna(role)
        },
        "radar_modes": [
            {"id": mode, "label": label} for mode, label in RADAR_MODES.items()
        ],
        "seasons": sorted(frame["season_name"].dropna().astype(str).unique(), reverse=True),
        "leagues": sorted(frame["competition_name"].dropna().astype(str).unique()),
        "league_seasons": {
            str(league): sorted(
                set(group["season_name"].dropna().astype(str))
                | set(group["candidate_window"].dropna().astype(str)),
                reverse=True,
            )
            for league, group in frame.groupby("competition_name", sort=True)
            if pd.notna(league)
        },
        "team_seasons": [
            {"team": team, "league": league, "season": season}
            for team, league, season in sorted(
                {
                    (str(row.team_name), str(row.competition_name), str(season))
                    for row in frame.itertuples()
                    if pd.notna(row.team_name) and pd.notna(row.competition_name)
                    for season in (row.season_name, row.candidate_window)
                    if pd.notna(season)
                },
                key=lambda item: (item[1], item[2], item[0]),
            )
        ],
        "positions": positions,
        "confidences": ["HIGH", "MEDIUM", "LOW"],
        "sort_fields": sorted(INTELLIGENCE_SORT_FIELDS),
        "player_sort_fields": sorted(PLAYER_SORT_FIELDS),
        "recruitment_sort_fields": sorted(RECRUITMENT_SORT_FIELDS),
    }


@app.get("/league")
def league_explorer(
    _auth: Protected,
    league: str,
    season: str,
    minimum_minutes: Annotated[float, Query(ge=0)] = 900,
    limit_per_mode: Annotated[int, Query(ge=1, le=20)] = 5,
) -> dict[str, Any]:
    service = get_service()
    available = service.intelligence_frame[
        service.intelligence_frame["competition_name"] == league
    ]
    if available.empty:
        raise HTTPException(status_code=422, detail=f"Unknown league: {league}")
    seasons = set(available["season_name"].dropna().astype(str)) | set(
        available["candidate_window"].dropna().astype(str)
    )
    if season not in seasons:
        raise HTTPException(
            status_code=422,
            detail=f"Season {season} is unavailable for {league}",
        )
    result = service.league_explorer(
        league=league,
        season=season,
        minimum_minutes=minimum_minutes,
        limit_per_mode=limit_per_mode,
    )
    return {
        "engine": "SCOUTPRINT INTELLIGENCE",
        "league": league,
        "season": season,
        "minimum_minutes": minimum_minutes,
        "ranking_claim": (
            "Role-relative current evidence from the selected league-season; "
            "not ability, potential or a league-strength model."
        ),
        **result,
    }


@app.get("/team")
def team_explorer(
    _auth: Protected,
    team: str,
    league: str,
    season: str,
    minimum_minutes: Annotated[float, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> dict[str, Any]:
    service = get_service()
    available = service.intelligence_frame[
        (service.intelligence_frame["team_name"] == team)
        & (service.intelligence_frame["competition_name"] == league)
        & (
            (service.intelligence_frame["season_name"] == season)
            | (service.intelligence_frame["candidate_window"] == season)
        )
    ]
    if available.empty:
        raise HTTPException(
            status_code=422,
            detail=f"Team-season evidence is unavailable: {team}, {league}, {season}",
        )
    result = service.team_explorer(
        team=team,
        league=league,
        season=season,
        minimum_minutes=minimum_minutes,
        limit=limit,
    )
    return {
        "engine": "SCOUTPRINT INTELLIGENCE",
        "team": team,
        "league": league,
        "season": season,
        "minimum_minutes": minimum_minutes,
        "evidence_claim": (
            "Player-season evidence for the selected club label; Current Level is role-relative "
            "and role depth describes recorded usage, not tactical importance or squad quality."
        ),
        "unavailable": [
            "Recent results and team performance",
            "Team xG and shot profile",
            "Passing networks and tactical conclusions",
        ],
        **result,
    }


@app.get("/matches")
def matches(
    _auth: Protected,
    league: str | None = None,
    team: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not exceed date_to")
    service = get_match_service()
    available_leagues = sorted(
        {
            str(row["league"].get("name"))
            for row in service.matches.values()
            if row["league"].get("name")
        }
    )
    if league and league not in available_leagues:
        raise HTTPException(status_code=422, detail=f"Unknown supported match league: {league}")
    rows, total = service.browse(
        league=league,
        team=team,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit,
    )
    dates = sorted(str(row.get("date")) for row in service.matches.values() if row.get("date"))
    return {
        "engine": "SCOUTPRINT MATCH EVIDENCE",
        "filters": {
            "league": league,
            "team": team,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
        "catalogue": {
            "leagues": available_leagues,
            "date_min": dates[0] if dates else None,
            "date_max": dates[-1] if dates else None,
            "supported_matches": len(service.matches),
        },
        "total": total,
        "offset": offset,
        "limit": limit,
        "matches": rows,
    }


@app.get("/matches/{match_id}")
def match_detail(match_id: str, _auth: Protected) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", match_id):
        raise HTTPException(status_code=404, detail="Supported match not found")
    return get_match_service().detail(match_id)


@app.get("/radar")
def radar(
    _auth: Protected,
    mode: str = "breakouts",
    season: str | None = None,
    league: str | None = None,
    minimum_age: Annotated[float | None, Query(ge=10, le=60)] = None,
    maximum_age: Annotated[float | None, Query(ge=10, le=60)] = None,
    role: str | None = None,
    position: str | None = None,
    minimum_minutes: Annotated[float, Query(ge=0)] = 0,
    confidence: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    if mode not in RADAR_MODES:
        raise HTTPException(status_code=422, detail=f"Unknown Radar mode: {mode}")
    if minimum_age is not None and maximum_age is not None and minimum_age > maximum_age:
        raise HTTPException(status_code=422, detail="minimum_age must not exceed maximum_age")
    normalized_confidence = confidence.upper() if confidence else None
    if normalized_confidence and normalized_confidence not in {"HIGH", "MEDIUM", "LOW"}:
        raise HTTPException(status_code=422, detail="confidence must be HIGH, MEDIUM or LOW")
    selected_sort = sort_by or RADAR_DEFAULT_SORTS[mode]
    if selected_sort not in INTELLIGENCE_SORT_FIELDS:
        raise HTTPException(status_code=422, detail=f"Unsupported Radar sort field: {selected_sort}")
    if sort_order not in {"asc", "desc"}:
        raise HTTPException(status_code=422, detail="sort_order must be asc or desc")

    service = get_service()
    rows, total, ranking = service.radar(
        mode=mode,
        season=season,
        league=league,
        minimum_age=minimum_age,
        maximum_age=maximum_age,
        role=role,
        position=position,
        minimum_minutes=minimum_minutes,
        confidence=normalized_confidence,
        sort_by=selected_sort,
        sort_order=sort_order,
        offset=offset,
        limit=limit,
    )
    return {
        "engine": "SCOUTPRINT INTELLIGENCE",
        "mode": {"id": mode, "label": RADAR_MODES[mode]},
        "filters": {
            "season": season,
            "league": league,
            "minimum_age": minimum_age,
            "maximum_age": maximum_age,
            "role": role,
            "position": position,
            "minimum_minutes": minimum_minutes,
            "confidence": normalized_confidence,
        },
        "sort": {"field": selected_sort, "order": sort_order},
        "score_model": RADAR_SCORE_MODEL,
        **ranking,
        "total": total,
        "offset": offset,
        "limit": limit,
        "results": [service.intelligence_record(row) for _, row in rows.iterrows()],
    }


@app.get("/players")
def players(
    _auth: Protected,
    name: str | None = None,
    player: str | None = None,
    club: str | None = None,
    league: str | None = None,
    competition: str | None = None,
    season: str | None = None,
    minimum_age: Annotated[float | None, Query(ge=10, le=60)] = None,
    maximum_age: Annotated[float | None, Query(ge=10, le=60)] = None,
    role: str | None = None,
    position: str | None = None,
    minimum_minutes: Annotated[float, Query(ge=0)] = 0,
    data_tier: str | None = None,
    confidence: str | None = None,
    sort_by: str = "radar_score",
    sort_order: str = "desc",
    unique_players: bool = True,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict[str, Any]:
    if minimum_age is not None and maximum_age is not None and minimum_age > maximum_age:
        raise HTTPException(status_code=422, detail="minimum_age must not exceed maximum_age")
    if player and name and player != name:
        raise HTTPException(status_code=422, detail="player and legacy name filters disagree")
    selected_league = league or competition
    if league and competition and league != competition:
        raise HTTPException(status_code=422, detail="league and legacy competition filters disagree")
    normalized_tier = data_tier.upper() if data_tier else None
    if normalized_tier and normalized_tier not in {"A", "B", "C"}:
        raise HTTPException(status_code=422, detail="data_tier must be A, B or C")
    normalized_confidence = confidence.upper() if confidence else None
    if normalized_confidence and normalized_confidence not in {"HIGH", "MEDIUM", "LOW"}:
        raise HTTPException(status_code=422, detail="confidence must be HIGH, MEDIUM or LOW")
    if sort_by not in PLAYER_SORT_FIELDS:
        raise HTTPException(status_code=422, detail=f"Unsupported Player sort field: {sort_by}")
    if sort_order not in {"asc", "desc"}:
        raise HTTPException(status_code=422, detail="sort_order must be asc or desc")

    service = get_service()
    rows, total, player_seasons = service.player_explorer(
        player=player or name,
        club=club,
        league=selected_league,
        season=season,
        minimum_age=minimum_age,
        maximum_age=maximum_age,
        role=role,
        position=position,
        minimum_minutes=minimum_minutes,
        data_tier=normalized_tier,
        confidence=normalized_confidence,
        sort_by=sort_by,
        sort_order=sort_order,
        unique_players=unique_players,
        offset=offset,
        limit=limit,
    )
    results = [service.player_explorer_record(row) for _, row in rows.iterrows()]
    return {
        "engine": "SCOUTPRINT INTELLIGENCE",
        "filters": {
            "player": player or name,
            "club": club,
            "league": selected_league,
            "season": season,
            "minimum_age": minimum_age,
            "maximum_age": maximum_age,
            "role": role,
            "position": position,
            "minimum_minutes": minimum_minutes,
            "data_tier": normalized_tier,
            "confidence": normalized_confidence,
        },
        "sort": {"field": sort_by, "order": sort_order},
        "unique_players": unique_players,
        "player_seasons": player_seasons,
        "total": total,
        "offset": offset,
        "limit": limit,
        "players": results,
    }


@app.get("/recruitment/roles")
def recruitment_roles(
    _auth: Protected,
    role: str,
    league: Annotated[list[str] | None, Query()] = None,
    season: str | None = None,
    minimum_age: Annotated[float | None, Query(ge=10, le=60)] = None,
    maximum_age: Annotated[float | None, Query(ge=10, le=60)] = None,
    minimum_minutes: Annotated[float, Query(ge=0)] = 0,
    sort_by: str = "current_level",
    sort_order: str = "desc",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    if minimum_age is not None and maximum_age is not None and minimum_age > maximum_age:
        raise HTTPException(status_code=422, detail="minimum_age must not exceed maximum_age")
    if sort_by not in RECRUITMENT_SORT_FIELDS:
        raise HTTPException(
            status_code=422, detail=f"Unsupported recruitment sort field: {sort_by}"
        )
    if sort_order not in {"asc", "desc"}:
        raise HTTPException(status_code=422, detail="sort_order must be asc or desc")

    service = get_service()
    available_roles = set(service.intelligence_frame["primary_role"].dropna().astype(str))
    if role not in available_roles:
        raise HTTPException(status_code=422, detail=f"Unknown recruitment role: {role}")
    selected_leagues = list(dict.fromkeys(league or []))
    available_leagues = set(
        service.intelligence_frame["competition_name"].dropna().astype(str)
    )
    unknown_leagues = sorted(set(selected_leagues) - available_leagues)
    if unknown_leagues:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown recruitment league: {', '.join(unknown_leagues)}",
        )

    rows, total, player_seasons = service.role_search(
        role=role,
        leagues=selected_leagues,
        season=season,
        minimum_age=minimum_age,
        maximum_age=maximum_age,
        minimum_minutes=minimum_minutes,
        sort_by=sort_by,
        sort_order=sort_order,
        offset=offset,
        limit=limit,
    )
    return {
        "engine": "SCOUTPRINT INTELLIGENCE",
        "filters": {
            "role": role,
            "leagues": selected_leagues,
            "season": season,
            "minimum_age": minimum_age,
            "maximum_age": maximum_age,
            "minimum_minutes": minimum_minutes,
        },
        "sort": {"field": sort_by, "order": sort_order},
        "role_fit_model": ROLE_FIT_MODEL,
        "player_seasons": player_seasons,
        "total": total,
        "offset": offset,
        "limit": limit,
        "candidates": [service.role_search_record(row) for _, row in rows.iterrows()],
    }


@app.get("/player/{player_season_id}/profile")
def player_profile(player_season_id: str, _auth: Protected) -> dict[str, Any]:
    return {"engine": "EXACT SCOUTPRINT", "profile": get_service().profile_by_id(player_season_id)}


@app.get("/player/{player_season_id}/intelligence")
def player_intelligence(player_season_id: str, _auth: Protected) -> dict[str, Any]:
    return {
        "engine": "SCOUTPRINT INTELLIGENCE",
        "intelligence": get_service().intelligence_by_player_season(player_season_id),
    }


@app.post("/search/similar")
def search_similar(request: SimilarSearchRequest, _auth: Protected) -> dict[str, Any]:
    service = get_service()
    ranked, runtime_ms = service.run_search(request)
    limited = ranked.head(request.result_limit)
    return {
        "engine": "EXACT SCOUTPRINT",
        "authoritative": True,
        "method": (
            "canonical self-exclusion, functional-role compatibility, fast profile prefilter, "
            "exact shortlisted Sinkhorn/cosine/JS reranking, evidence-and-role-adjusted recommendation"
        ),
        "runtime_ms": round(runtime_ms, 1),
        "candidate_count": len(ranked),
        "results": [service.result(row, rank) for rank, (_, row) in enumerate(limited.iterrows(), 1)],
    }


def _explanation(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    measured = []
    labels = {
        "pct_half_space": "half-space involvement",
        "pct_penalty_area": "penalty-area presence",
        "pct_wide": "wide activity",
        "shots_p90": "shot volume",
        "chance_creation_p90": "chance creation",
    }
    a_stats, b_stats = reference["statistics"], candidate["statistics"]
    for key, label in labels.items():
        a_value, b_value = a_stats.get(key), b_stats.get(key)
        if a_value is None or b_value is None:
            continue
        delta = b_value - a_value
        threshold = max(abs(a_value) * 0.12, 0.015 if key.startswith("pct_") else 0.08)
        direction = "similar" if abs(delta) < threshold else ("more" if delta > 0 else "less")
        measured.append({"metric": key, "label": label, "direction": direction, "delta": delta})
    text = ", ".join(f"{item['direction']} {item['label']}" for item in measured[:4])
    return {
        "text": f"{candidate['player_name']} compares through {text or 'the available profile dimensions'}.",
        "measured_differences": measured,
    }


@app.post("/comparison")
def comparison(request: ComparisonRequest, _auth: Protected) -> dict[str, Any]:
    service = get_service()
    ranked, runtime_ms = service.run_search(request)
    candidate_rows = ranked[ranked["player_season_id"] == request.candidate_player_season_id]
    if candidate_rows.empty:
        raise HTTPException(status_code=404, detail="Candidate is not in the exact shortlist")
    candidate_row = candidate_rows.iloc[0]
    candidate_rank = int(ranked.index.get_loc(candidate_rows.index[0])) + 1
    reference = service.profile_by_id(request.reference_player_season_id)
    candidate = service.profile_by_id(request.candidate_player_season_id)
    difference_maps = {}
    for name in MAP_FIELDS:
        a_map, b_map = reference["maps"].get(name), candidate["maps"].get(name)
        difference_maps[name] = (
            None
            if a_map is None or b_map is None
            else [round(b - a, 12) for a, b in zip(a_map, b_map, strict=True)]
        )
    return {
        "engine": "EXACT SCOUTPRINT",
        "authoritative": True,
        "runtime_ms": round(runtime_ms, 1),
        "score": service.result(candidate_row, candidate_rank),
        "reference": reference,
        "candidate": candidate,
        "difference_maps": difference_maps,
        "explanation": _explanation(reference, candidate),
    }
