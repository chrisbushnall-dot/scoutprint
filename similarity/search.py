from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler

from similarity.spatial import cosine_score, js_score, mirrored, role_scores

CATEGORY_METRICS = {
    "Goal threat": ["goals_p90", "xg_p90", "pct_penalty_area", "box_presence_rate"],
    "Shooting": ["shots_p90", "xg_p90"],
    "Chance creation": ["chance_creation_p90", "assists_p90"],
    "Carrying": ["carries_p90"],
    "Passing": ["passes_p90"],
    "Defending": ["defensive_actions_p90"],
}


def _category_scores(frame: pd.DataFrame, reference_index: int) -> dict[str, np.ndarray]:
    scores: dict[str, np.ndarray] = {}
    for category, metrics in CATEGORY_METRICS.items():
        available = [m for m in metrics if m in frame and frame[m].notna().sum() >= 2]
        if not available:
            scores[category] = np.full(len(frame), 50.0)
            continue
        values = frame[available].fillna(frame[available].median()).to_numpy(dtype=float)
        scaled = RobustScaler(quantile_range=(10, 90)).fit_transform(values)
        distance = np.sqrt(np.mean((scaled - scaled[reference_index]) ** 2, axis=1))
        scores[category] = 100 * np.exp(-distance)
    return scores


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
    reference_grid = np.asarray(reference["fp_all_actions"], dtype=float).reshape(
        int(reference["grid_x"]), int(reference["grid_y"])
    )
    prefilter = []
    for _, candidate in frame.iterrows():
        grid = np.asarray(candidate["fp_all_actions"], dtype=float).reshape(
            int(candidate["grid_x"]), int(candidate["grid_y"])
        )
        same_fast = 0.6 * cosine_score(reference_grid, grid) + 0.4 * js_score(reference_grid, grid)
        mirror_grid = mirrored(grid)
        mirror_fast = 0.6 * cosine_score(reference_grid, mirror_grid) + 0.4 * js_score(
            reference_grid, mirror_grid
        )
        prefilter.append(max(same_fast, mirror_fast) if mirror_mode else same_fast)
    frame["_prefilter"] = prefilter
    if len(frame) > max_spatial_candidates + 1:
        keep_ids = set(frame.nlargest(max_spatial_candidates, "_prefilter")["player_season_id"]) | {
            reference_id
        }
        frame = frame[frame["player_season_id"].isin(keep_ids)].reset_index(drop=True)
        reference_index = frame.index[frame["player_season_id"] == reference_id][0]
        reference = frame.loc[reference_index]
        reference_grid = np.asarray(reference["fp_all_actions"], dtype=float).reshape(
            int(reference["grid_x"]), int(reference["grid_y"])
        )
    same_scores, mirror_scores, role = [], [], []
    for _, candidate in frame.iterrows():
        grid = np.asarray(candidate["fp_all_actions"], dtype=float).reshape(
            int(candidate["grid_x"]), int(candidate["grid_y"])
        )
        spatial = role_scores(reference_grid, grid)
        same_scores.append(spatial["same_side"])
        mirror_scores.append(spatial["mirrored"])
        role.append(spatial["role"] if mirror_mode else spatial["same_side"])
    frame["Same-side"], frame["Mirrored"], frame["Spatial role"] = same_scores, mirror_scores, role
    for category, values in _category_scores(frame, reference_index).items():
        frame[category] = values
    total_weight = sum(weights.values()) or 1.0
    frame["Overall"] = (
        sum(frame[category] * weight for category, weight in weights.items()) / total_weight
    )
    return frame[frame["player_season_id"] != reference_id].sort_values("Overall", ascending=False)
