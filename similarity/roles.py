from __future__ import annotations

import re
from collections.abc import Iterable

import numpy as np
import pandas as pd

ROLE_LABELS = {
    "attacking_wide": "Attacking wide / inside forward",
    "creative_attacker": "Creative attacker / #10",
    "centre_forward": "Centre forward",
    "central_midfielder": "Central / progressive midfielder",
    "defensive_midfielder": "Deep / defensive midfielder",
    "fullback": "Fullback / wingback",
    "centre_back": "Centre back",
}

ROLE_KEYS = list(ROLE_LABELS)


def _contains(position: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, position) for pattern in patterns)


def _percentile(frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    available = [column for column in columns if column in frame and frame[column].notna().any()]
    if not available:
        return np.zeros(len(frame))
    ranked = [frame[column].rank(pct=True).to_numpy(dtype=float) for column in available]
    matrix = np.vstack(ranked)
    comparable = np.isfinite(matrix)
    values = np.divide(
        np.nansum(matrix, axis=0),
        comparable.sum(axis=0),
        out=np.zeros(len(frame)),
        where=comparable.sum(axis=0) > 0,
    )
    return values


def role_profiles(frame: pd.DataFrame) -> pd.DataFrame:
    """Infer broad, overlapping functional roles from position and observable behaviour.

    Provider position strings provide priors, while production, creation, involvement,
    progression and defending add supporting evidence. Missing metrics add no evidence.
    The roles are deliberately broad and allow mirrored sides.
    """

    scores = pd.DataFrame(0.0, index=frame.index, columns=ROLE_KEYS)
    positions = frame.get("positions", pd.Series("", index=frame.index)).fillna("").astype(str)
    for index, raw_position in positions.items():
        position = raw_position.casefold().replace("_", " ")
        if _contains(position, [r"goalkeeper", r"\bgk\b"]):
            continue
        if _contains(position, [r"centre back", r"center back", r"\bcb\b"]):
            scores.at[index, "centre_back"] = 0.95
            scores.at[index, "defensive_midfielder"] = 0.25
            scores.at[index, "fullback"] = 0.15
        if _contains(
            position,
            [r"full.?back", r"wing.?back", r"left back", r"right back", r"\blwb\b", r"\brwb\b", r"\blb\b", r"\brb\b"],
        ):
            scores.at[index, "fullback"] = max(scores.at[index, "fullback"], 0.95)
            scores.at[index, "attacking_wide"] = max(
                scores.at[index, "attacking_wide"], 0.3
            )
            scores.at[index, "central_midfielder"] = max(
                scores.at[index, "central_midfielder"], 0.2
            )
        if _contains(
            position,
            [r"defensive midfield", r"holding midfield", r"\bdm\b", r"\bcdm\b"],
        ):
            scores.at[index, "defensive_midfielder"] = max(
                scores.at[index, "defensive_midfielder"], 0.9
            )
            scores.at[index, "central_midfielder"] = max(
                scores.at[index, "central_midfielder"], 0.65
            )
        if _contains(
            position,
            [r"central midfield", r"centre midfield", r"center midfield", r"\bcm\b", r"midfielder", r"\bm\b"],
        ):
            scores.at[index, "central_midfielder"] = max(
                scores.at[index, "central_midfielder"], 0.85
            )
            scores.at[index, "defensive_midfielder"] = max(
                scores.at[index, "defensive_midfielder"], 0.35
            )
            scores.at[index, "creative_attacker"] = max(
                scores.at[index, "creative_attacker"], 0.35
            )
        if _contains(
            position,
            [r"attacking midfield", r"offensive midfield", r"\bam\b", r"\bcam\b", r"number 10", r"#10"],
        ):
            scores.at[index, "creative_attacker"] = max(
                scores.at[index, "creative_attacker"], 0.9
            )
            scores.at[index, "central_midfielder"] = max(
                scores.at[index, "central_midfielder"], 0.5
            )
            scores.at[index, "attacking_wide"] = max(
                scores.at[index, "attacking_wide"], 0.4
            )
        if _contains(
            position,
            [r"wing", r"wide", r"inside forward", r"\blw\b", r"\brw\b", r"^w$", r"\bw\b"],
        ):
            scores.at[index, "attacking_wide"] = max(
                scores.at[index, "attacking_wide"], 0.9
            )
            scores.at[index, "creative_attacker"] = max(
                scores.at[index, "creative_attacker"], 0.55
            )
            scores.at[index, "centre_forward"] = max(
                scores.at[index, "centre_forward"], 0.35
            )
        if _contains(
            position,
            [r"striker", r"centre forward", r"center forward", r"\bst\b", r"\bcf\b", r"forward"],
        ):
            scores.at[index, "centre_forward"] = max(
                scores.at[index, "centre_forward"], 0.9
            )
            scores.at[index, "attacking_wide"] = max(
                scores.at[index, "attacking_wide"], 0.35
            )
            scores.at[index, "creative_attacker"] = max(
                scores.at[index, "creative_attacker"], 0.35
            )

    goal_threat = _percentile(frame, ["goals_p90", "xg_p90", "shots_p90", "box_presence_rate"])
    creation = _percentile(frame, ["assists_p90", "xa_p90", "chance_creation_p90"])
    progression = _percentile(frame, ["progressions_p90", "carries_p90", "dribbles_p90"])
    passing = _percentile(frame, ["passes_p90"])
    defending = _percentile(frame, ["defensive_actions_p90"])
    width = _percentile(frame, ["pct_wide"])

    scores["centre_forward"] += 0.35 * goal_threat
    scores["attacking_wide"] += 0.22 * goal_threat + 0.28 * progression + 0.12 * width
    scores["creative_attacker"] += 0.38 * creation + 0.18 * progression + 0.1 * passing
    scores["central_midfielder"] += 0.25 * progression + 0.25 * passing + 0.1 * creation
    scores["defensive_midfielder"] += 0.25 * defending + 0.18 * passing
    scores["fullback"] += 0.2 * defending + 0.16 * progression + 0.12 * width
    scores["centre_back"] += 0.32 * defending + 0.12 * passing
    return scores.clip(upper=1.0)


def add_role_compatibility(
    frame: pd.DataFrame, reference_id: str
) -> tuple[pd.DataFrame, dict[str, float]]:
    profiles = role_profiles(frame)
    reference_rows = frame.index[frame["player_season_id"] == reference_id].tolist()
    if not reference_rows:
        raise KeyError(f"Unknown reference player-season: {reference_id}")
    reference_vector = profiles.loc[reference_rows[0]].to_numpy(dtype=float)
    reference_norm = np.linalg.norm(reference_vector)
    candidate_values = profiles.to_numpy(dtype=float)
    candidate_norms = np.linalg.norm(candidate_values, axis=1)
    compatibility = np.divide(
        candidate_values @ reference_vector,
        candidate_norms * reference_norm,
        out=np.zeros(len(frame)),
        where=(candidate_norms > 0) & (reference_norm > 0),
    )
    output = frame.copy()
    output["Role compatibility"] = 100 * compatibility
    output["Role family"] = [
        ROLE_LABELS[ROLE_KEYS[int(np.argmax(row))]] if np.max(row) > 0 else "Unclassified"
        for row in candidate_values
    ]
    output["Role confidence"] = np.max(candidate_values, axis=1)
    return output, {
        ROLE_LABELS[key]: round(float(value) * 100, 1)
        for key, value in zip(ROLE_KEYS, reference_vector, strict=True)
        if value >= 0.35
    }
