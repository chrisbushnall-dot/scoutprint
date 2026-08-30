from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler

from similarity.spatial import cosine_score, js_score, mirrored, role_scores

CATEGORY_METRICS = {
    "Goal threat": ["goals_p90", "xg_p90", "pct_penalty_area", "box_presence_rate"],
    "Shooting": ["shots_p90", "xg_p90"],
    "Chance creation": ["chance_creation_p90", "assists_p90"],
    "Carrying": ["carries_p90", "progressions_p90", "dribbles_p90"],
    "Passing": ["passes_p90"],
    "Defending": ["defensive_actions_p90"],
}


def _category_scores(
    frame: pd.DataFrame, reference_index: int
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    scores: dict[str, np.ndarray] = {}
    completeness: dict[str, np.ndarray] = {}
    for category, metrics in CATEGORY_METRICS.items():
        available = [
            metric
            for metric in metrics
            if metric in frame
            and frame[metric].notna().sum() >= 2
            and pd.notna(frame.at[reference_index, metric])
        ]
        if not available:
            scores[category] = np.full(len(frame), np.nan)
            completeness[category] = np.zeros(len(frame))
            continue
        values = frame[available].to_numpy(dtype=float)
        scaled = RobustScaler(quantile_range=(10, 90)).fit_transform(values)
        squared_difference = (scaled - scaled[reference_index]) ** 2
        comparable = np.isfinite(squared_difference)
        comparable_count = comparable.sum(axis=1)
        distance = np.sqrt(
            np.divide(
                np.nansum(squared_difference, axis=1),
                comparable_count,
                out=np.full(len(frame), np.nan),
                where=comparable_count > 0,
            )
        )
        scores[category] = 100 * np.exp(-distance)
        completeness[category] = comparable_count / len(available)
    return scores, completeness


def rank_similar(
    frame: pd.DataFrame,
    reference_id: str,
    weights: dict[str, float],
    min_minutes: float = 0,
    mirror_mode: bool = True,
    max_spatial_candidates: int = 80,
) -> pd.DataFrame:
    reference_source = frame.loc[frame["player_season_id"] == reference_id]
    frame = (
        pd.concat([frame.loc[frame["minutes"] >= min_minutes], reference_source])
        .drop_duplicates("player_season_id")
        .reset_index(drop=True)
    )
    matches = frame.index[frame["player_season_id"] == reference_id].tolist()
    if not matches:
        raise KeyError(f"Unknown reference player-season: {reference_id}")
    reference_index = matches[0]
    reference = frame.loc[reference_index]

    def spatial_grid(row: pd.Series) -> np.ndarray | None:
        vector = row.get("fp_all_actions")
        availability = row.get("spatial_available")
        if vector is None or (
            availability is not None and pd.notna(availability) and not bool(availability)
        ):
            return None
        try:
            grid_x, grid_y = int(row["grid_x"]), int(row["grid_y"])
            grid = np.asarray(vector, dtype=float).reshape(grid_x, grid_y)
        except (TypeError, ValueError):
            return None
        return grid if np.isfinite(grid).all() and grid.sum() > 0 else None

    reference_grid = spatial_grid(reference)
    frame["_prefilter"] = np.nan
    frame["Same-side"] = np.nan
    frame["Mirrored"] = np.nan
    frame["Spatial role"] = np.nan
    spatial_shortlist: set[int] = set()
    if reference_grid is not None:
        prefilter: dict[int, float] = {}
        for index, candidate in frame.iterrows():
            grid = spatial_grid(candidate)
            if grid is None or grid.shape != reference_grid.shape:
                continue
            same_fast = 0.6 * cosine_score(reference_grid, grid) + 0.4 * js_score(
                reference_grid, grid
            )
            mirror_grid = mirrored(grid)
            mirror_fast = 0.6 * cosine_score(reference_grid, mirror_grid) + 0.4 * js_score(
                reference_grid, mirror_grid
            )
            prefilter[index] = max(same_fast, mirror_fast) if mirror_mode else same_fast
        if prefilter:
            ordered = sorted(prefilter, key=prefilter.get, reverse=True)
            spatial_shortlist = set(ordered[: max_spatial_candidates + 1]) | {reference_index}
            for index, value in prefilter.items():
                frame.at[index, "_prefilter"] = value
        for index in spatial_shortlist:
            grid = spatial_grid(frame.loc[index])
            if grid is None or grid.shape != reference_grid.shape:
                continue
            spatial = role_scores(reference_grid, grid)
            frame.at[index, "Same-side"] = spatial["same_side"]
            frame.at[index, "Mirrored"] = spatial["mirrored"]
            frame.at[index, "Spatial role"] = (
                spatial["role"] if mirror_mode else spatial["same_side"]
            )
    category_scores, category_completeness = _category_scores(frame, reference_index)
    for category, values in category_scores.items():
        frame[category] = values
    total_weight = sum(weights.values()) or 1.0
    weighted_score = np.zeros(len(frame))
    comparable_weight = np.zeros(len(frame))
    coverage_weight = np.zeros(len(frame))
    missing_by_row: list[list[str]] = [[] for _ in range(len(frame))]
    spatial_available = (
        frame["spatial_available"].fillna(False).to_numpy(dtype=bool)
        if "spatial_available" in frame
        else np.ones(len(frame), dtype=bool)
    )
    for category, weight in weights.items():
        values = frame[category].to_numpy(dtype=float)
        valid = np.isfinite(values)
        weighted_score += np.where(valid, values * weight, 0.0)
        comparable_weight += np.where(valid, weight, 0.0)
        if category == "Spatial role":
            category_coverage = spatial_available.astype(float)
        else:
            category_coverage = category_completeness.get(category, np.zeros(len(frame)))
        coverage_weight += category_coverage * weight
        for index in np.flatnonzero(~valid):
            missing_by_row[index].append(category)
    frame["Overall"] = np.divide(
        weighted_score,
        comparable_weight,
        out=np.full(len(frame), np.nan),
        where=comparable_weight > 0,
    )
    frame["Comparable profile coverage"] = 100 * coverage_weight / total_weight
    frame["Unavailable dimensions"] = [", ".join(items) or "None" for items in missing_by_row]
    return frame[frame["player_season_id"] != reference_id].sort_values(
        ["Overall", "Comparable profile coverage"], ascending=[False, False]
    )
