from __future__ import annotations

import hmac
import math
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import pandas as pd
import polars as pl
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

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
    minimum_minutes: float = Field(default=0, ge=0)
    minimum_age: float | None = Field(default=None, ge=10, le=60)
    maximum_age: float | None = Field(default=None, ge=10, le=60)
    mirror_mode: bool = True
    minimum_comparison_coverage: float = Field(default=0, ge=0, le=100)
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
        self.by_id = frame.set_index("player_season_id", drop=False)

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
        candidates = self.frame
        if request.candidate_competitions:
            candidates = candidates[
                candidates["competition_name"].isin(request.candidate_competitions)
            ]
        if request.candidate_seasons:
            candidates = candidates[candidates["season_name"].isin(request.candidate_seasons)]
        candidates = candidates[candidates["minutes"].fillna(-1) >= request.minimum_minutes]
        if request.minimum_age is not None:
            candidates = candidates[candidates["age"].notna()]
            candidates = candidates[candidates["age"] >= request.minimum_age]
        if request.maximum_age is not None:
            candidates = candidates[candidates["age"].notna()]
            candidates = candidates[candidates["age"] <= request.maximum_age]
        reference_frame = self.by_id.loc[[request.reference_player_season_id]].reset_index(drop=True)
        return (
            pd.concat([candidates, reference_frame], ignore_index=True)
            .drop_duplicates("player_season_id")
            .reset_index(drop=True),
            reference,
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
        return ranked, (time.perf_counter() - started) * 1000

    def result(self, row: pd.Series, rank: int) -> dict[str, Any]:
        categories = {
            category: _safe(row.get(category))
            for category in ["Spatial role", *CATEGORY_METRICS]
            if _safe(row.get(category)) is not None
        }
        missing = str(row.get("Unavailable dimensions") or "None")
        return {
            "rank": rank,
            "player_season_id": row["player_season_id"],
            "canonical_player_id": row.get("canonical_player_id"),
            "player_name": row["player_name"],
            "club": row.get("team_name"),
            "competition": row.get("competition_name"),
            "season": row.get("season_name"),
            "position": row.get("positions"),
            "age": _safe(row.get("age")),
            "minutes": _safe(row.get("minutes")),
            "profile_match": _safe(row.get("Overall")),
            "spatial_match": _safe(row.get("Spatial role")),
            "same_side_match": _safe(row.get("Same-side")),
            "mirrored_match": _safe(row.get("Mirrored")),
            "category_similarities": categories,
            "comparison_coverage": _safe(row.get("Comparable profile coverage")),
            "xg": _safe(row.get("xg")),
            "xa": _safe(row.get("xa")),
            "xg_p90": _safe(row.get("xg_p90")),
            "xa_p90": _safe(row.get("xa_p90")),
            "unavailable_categories": [] if missing == "None" else missing.split(", "),
        }

    def compact_profile(self, row: pd.Series) -> dict[str, Any]:
        maps = {name: _safe(row.get(column)) for name, column in MAP_FIELDS.items()}
        stats = {field: _safe(row.get(field)) for field in STAT_FIELDS}
        available = {
            field.removesuffix("_available"): bool(_safe(row.get(field)) or False)
            for field in AVAILABILITY_FIELDS
        }
        return {
            **{field: _safe(row.get(field)) for field in PROFILE_FIELDS},
            "grid": [int(row["grid_x"]), int(row["grid_y"])],
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


@app.get("/players")
def players(
    _auth: Protected,
    name: str | None = None,
    competition: str | None = None,
    season: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict[str, Any]:
    frame = get_service().frame
    if name:
        frame = frame[frame["player_name"].str.contains(name, case=False, regex=False, na=False)]
    if competition:
        frame = frame[frame["competition_name"] == competition]
    if season:
        frame = frame[frame["season_name"] == season]
    frame = frame.sort_values(["player_name", "season_name"]).head(limit)
    return {
        "players": [
            {field: _safe(row.get(field)) for field in PROFILE_FIELDS}
            for _, row in frame.iterrows()
        ]
    }


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
        "method": "fast all-profile prefilter then exact shortlisted Sinkhorn/cosine/JS reranking",
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
