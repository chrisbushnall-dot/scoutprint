from __future__ import annotations

import hmac
import math
import os
import re
import time
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import pandas as pd
import polars as pl
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from similarity.roles import add_role_compatibility
from similarity.search import CATEGORY_METRICS, rank_similar

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
    def __init__(self, history_path: Path):
        if not history_path.exists():
            raise FileNotFoundError(f"Canonical player history not found: {history_path}")
        frame = pl.read_parquet(history_path).to_pandas()
        primary = frame[frame["is_primary_profile"].fillna(False)].copy()
        self.frame = primary.reset_index(drop=True)
        self.frame["candidate_window"] = self.frame.apply(self._candidate_window, axis=1)
        self.frame["canonical_person_id"] = self._canonical_person_ids(self.frame)
        self.by_id = self.frame.set_index("player_season_id", drop=False)

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
        output["Recommendation"] = output["Overall"] * output["Confidence factor"]
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


@lru_cache(maxsize=1)
def get_service() -> ExactScoutprintService:
    history_path = Path(
        os.getenv(
            "FOOTBALL_SCOUT_HISTORY",
            "data/private/canonical_identity/player_season_history.parquet",
        )
    )
    return ExactScoutprintService(history_path)


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


@app.get("/players")
def players(
    _auth: Protected,
    name: str | None = None,
    competition: str | None = None,
    season: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict[str, Any]:
    frame = get_service().frame
    matched = frame
    if name:
        matched = matched[
            matched["player_name"].str.contains(name, case=False, regex=False, na=False)
        ]
    if competition:
        matched = matched[matched["competition_name"] == competition]
    if season:
        matched = matched[matched["season_name"] == season]
    person_ids = matched["canonical_person_id"].dropna().drop_duplicates().head(limit)
    frame = frame[frame["canonical_person_id"].isin(person_ids)]
    summaries = []
    for person_id, group in frame.groupby("canonical_person_id", sort=False):
        names = sorted(
            set(group["player_name"].dropna().astype(str)),
            key=lambda value: ("\\u" in value, len(value.split()), len(value), value),
        )
        profiles = group.sort_values(
            ["season_start_year", "competition_name"], ascending=[False, True]
        )
        profile_rows = [
            {
                **{field: _safe(row.get(field)) for field in PROFILE_FIELDS},
                "canonical_player_id": person_id,
            }
            for _, row in profiles.iterrows()
        ]
        summaries.append(
            {
                "canonical_player_id": person_id,
                "player_name": names[0] if names else "Unknown player",
                "clubs": sorted(set(group["team_name"].dropna().astype(str))),
                "competitions": sorted(
                    set(group["competition_name"].dropna().astype(str))
                ),
                "season_count": int(group["season_name"].nunique()),
                "profile_count": len(group),
                "profiles": profile_rows,
            }
        )
    summaries.sort(key=lambda item: (item["player_name"].casefold(), item["canonical_player_id"]))
    return {"players": summaries[:limit]}


@app.get("/player/{player_season_id}/profile")
def player_profile(player_season_id: str, _auth: Protected) -> dict[str, Any]:
    return {"engine": "EXACT SCOUTPRINT", "profile": get_service().profile_by_id(player_season_id)}


@app.post("/search/similar")
def search_similar(request: SimilarSearchRequest, _auth: Protected) -> dict[str, Any]:
    service = get_service()
    ranked, runtime_ms = service.run_search(request)
    limited = ranked.head(request.result_limit)
    return {
        "engine": "EXACT SCOUTPRINT",
        "authoritative": True,
        "method": (
            "canonical self-exclusion, broad role compatibility, fast profile prefilter, "
            "exact shortlisted Sinkhorn/cosine/JS reranking, evidence-adjusted recommendation"
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
