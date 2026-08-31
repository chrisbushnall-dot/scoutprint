from __future__ import annotations

import re
from collections.abc import Iterable

import numpy as np
import pandas as pd

ROLE_LABELS = {
    "box_9": "Centre forward / box 9",
    "scoring_wide": "Scoring wide forward / inside forward",
    "creative_wide": "Creative wide forward",
    "second_striker": "Second striker",
    "creative_10": "Creative #10 / attacking midfielder",
    "hybrid_creator_scorer": "Hybrid creator-scorer",
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
    return np.divide(
        np.nansum(matrix, axis=0),
        comparable.sum(axis=0),
        out=np.zeros(len(frame)),
        where=comparable.sum(axis=0) > 0,
    )


def _trait(frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    """Return a behavioural percentile while preserving unavailable evidence as NaN."""

    available = [column for column in columns if column in frame and frame[column].notna().any()]
    if not available:
        return np.full(len(frame), np.nan)
    values = _percentile(frame, available)
    observed = frame[available].notna().any(axis=1).to_numpy()
    return np.where(observed, values, np.nan)


def functional_traits(frame: pd.DataFrame) -> pd.DataFrame:
    """Observable role signature used to compare how players function, not just labels."""

    return pd.DataFrame(
        {
            "scoring": _trait(frame, ["goals_p90", "xg_p90", "shots_p90"]),
            "creation": _trait(frame, ["assists_p90", "xa_p90", "chance_creation_p90"]),
            "progression": _trait(frame, ["progressions_p90", "carries_p90", "dribbles_p90"]),
            "involvement": _trait(frame, ["passes_p90", "receipts_p90"]),
            "box": _trait(frame, ["box_presence_rate", "pct_penalty_area", "pct_central"]),
            "half_space": _trait(frame, ["pct_half_space"]),
            "width": _trait(frame, ["pct_wide"]),
        },
        index=frame.index,
    )


def role_profiles(frame: pd.DataFrame) -> pd.DataFrame:
    """Infer overlapping functional roles from position and observable behaviour.

    Position is deliberately only a prior. Attacking roles are separated by scoring,
    creation, involvement, progression and spatial occupation so a provider's generic
    ``Forward``/``Center Forward`` label cannot make a box 9 equivalent to a hybrid creator.
    Missing metrics add no evidence and mirror-flank roles remain side-agnostic.
    """

    scores = pd.DataFrame(0.0, index=frame.index, columns=ROLE_KEYS)
    positions = frame.get("positions", pd.Series("", index=frame.index)).fillna("").astype(str)
    for index, raw_position in positions.items():
        position = raw_position.casefold().replace("_", " ")
        if _contains(position, [r"goalkeeper", r"\bgk\b"]):
            continue
        if _contains(position, [r"centre back", r"center back", r"\bcb\b"]):
            scores.at[index, "centre_back"] = 0.45
            scores.at[index, "defensive_midfielder"] = 0.08
        if _contains(
            position,
            [r"full.?back", r"wing.?back", r"left back", r"right back", r"\blwb\b", r"\brwb\b", r"\blb\b", r"\brb\b"],
        ):
            scores.at[index, "fullback"] = 0.45
            scores.at[index, "creative_wide"] = 0.08
        if _contains(
            position,
            [r"defensive midfield", r"holding midfield", r"\bdm\b", r"\bcdm\b"],
        ):
            scores.at[index, "defensive_midfielder"] = 0.42
            scores.at[index, "central_midfielder"] = 0.22
        if _contains(
            position,
            [r"central midfield", r"centre midfield", r"center midfield", r"\bcm\b", r"midfielder", r"\bm\b"],
        ):
            scores.at[index, "central_midfielder"] = max(
                scores.at[index, "central_midfielder"], 0.4
            )
            scores.at[index, "creative_10"] = max(scores.at[index, "creative_10"], 0.1)
        if _contains(
            position,
            [r"attacking midfield", r"offensive midfield", r"\bam\b", r"\bcam\b", r"number 10", r"#10"],
        ):
            scores.at[index, "creative_10"] = 0.35
            scores.at[index, "hybrid_creator_scorer"] = 0.14
            scores.at[index, "second_striker"] = 0.08
        if _contains(
            position,
            [r"wing", r"wide", r"inside forward", r"\blw\b", r"\brw\b", r"^w$", r"\bw\b"],
        ):
            scores.at[index, "scoring_wide"] = 0.28
            scores.at[index, "creative_wide"] = 0.28
            scores.at[index, "hybrid_creator_scorer"] = 0.12
        if _contains(
            position,
            [r"striker", r"centre forward", r"center forward", r"\bst\b", r"\bcf\b"],
        ):
            scores.at[index, "box_9"] = 0.28
            scores.at[index, "second_striker"] = 0.15
            scores.at[index, "hybrid_creator_scorer"] = 0.08
        elif _contains(position, [r"forward", r"\bf\b"]):
            # Generic provider labels are intentionally weak and behaviour must decide.
            scores.at[index, "box_9"] = 0.08
            scores.at[index, "scoring_wide"] = 0.08
            scores.at[index, "second_striker"] = 0.08
            scores.at[index, "hybrid_creator_scorer"] = 0.06

    goal_threat = _percentile(frame, ["goals_p90", "xg_p90", "shots_p90"])
    creation = _percentile(frame, ["assists_p90", "xa_p90", "chance_creation_p90"])
    progression = _percentile(frame, ["progressions_p90", "carries_p90", "dribbles_p90"])
    involvement = _percentile(frame, ["passes_p90", "receipts_p90"])
    box = _percentile(frame, ["box_presence_rate", "pct_penalty_area"])
    central = _percentile(frame, ["pct_central"])
    half_space = _percentile(frame, ["pct_half_space"])
    width = _percentile(frame, ["pct_wide"])
    defending = _percentile(frame, ["defensive_actions_p90"])
    wide_contrast = np.clip(width - 0.65 * central, 0, 1)
    central_contrast = np.clip(central - 0.65 * width, 0, 1)

    scores["box_9"] += 0.3 * goal_threat + 0.24 * box + 0.3 * central_contrast
    scores["scoring_wide"] += (
        0.27 * goal_threat + 0.38 * wide_contrast + 0.14 * half_space + 0.12 * progression
    )
    scores["creative_wide"] += (
        0.28 * creation + 0.21 * width + 0.18 * progression + 0.13 * involvement
    )
    scores["second_striker"] += (
        0.25 * goal_threat + 0.22 * creation + 0.17 * half_space + 0.1 * box
    )
    scores["creative_10"] += (
        0.32 * creation + 0.22 * involvement + 0.19 * progression + 0.09 * half_space
    )
    scores["hybrid_creator_scorer"] += (
        0.24 * goal_threat
        + 0.24 * creation
        + 0.18 * involvement
        + 0.18 * progression
        + 0.08 * half_space
    )
    scores["central_midfielder"] += (
        0.29 * involvement + 0.28 * progression + 0.12 * creation + 0.08 * defending
    )
    scores["defensive_midfielder"] += 0.29 * defending + 0.23 * involvement
    scores["fullback"] += 0.22 * defending + 0.2 * progression + 0.15 * width
    scores["centre_back"] += 0.36 * defending + 0.16 * involvement

    normalized_positions = positions.str.casefold().str.replace("_", " ", regex=False)
    explicit_centre_back = normalized_positions.str.contains(
        r"centre back|center back|\bcb\b", regex=True
    )
    explicit_fullback = normalized_positions.str.contains(
        r"full.?back|wing.?back|left back|right back|\blwb\b|\brwb\b|\blb\b|\brb\b",
        regex=True,
    )
    attacking_roles = [
        "box_9",
        "scoring_wide",
        "creative_wide",
        "second_striker",
        "creative_10",
        "hybrid_creator_scorer",
    ]
    # A strong explicit defensive position is contradictory evidence, not a rigid label.
    # It attenuates noisy attacking rates without erasing an attacking fullback profile.
    scores.loc[explicit_centre_back, attacking_roles] *= 0.18
    scores.loc[explicit_fullback, attacking_roles] *= 0.5
    return scores.clip(lower=0)


def add_role_compatibility(
    frame: pd.DataFrame, reference_id: str
) -> tuple[pd.DataFrame, dict[str, float]]:
    profiles = role_profiles(frame)
    reference_rows = frame.index[frame["player_season_id"] == reference_id].tolist()
    if not reference_rows:
        raise KeyError(f"Unknown reference player-season: {reference_id}")
    reference_vector = profiles.loc[reference_rows[0]].to_numpy(dtype=float)
    candidate_values = profiles.to_numpy(dtype=float)

    reference_norm = np.linalg.norm(reference_vector)
    candidate_norms = np.linalg.norm(candidate_values, axis=1)
    cosine = np.divide(
        candidate_values @ reference_vector,
        candidate_norms * reference_norm,
        out=np.zeros(len(frame)),
        where=(candidate_norms > 0) & (reference_norm > 0),
    )
    # Cubing the role scores makes dominant archetypes matter without forcing one label.
    sharpened_reference = reference_vector**3
    sharpened_candidates = candidate_values**3
    reference_share = np.divide(
        sharpened_reference,
        sharpened_reference.sum(),
        out=np.zeros_like(sharpened_reference),
        where=sharpened_reference.sum() > 0,
    )
    candidate_sums = sharpened_candidates.sum(axis=1, keepdims=True)
    candidate_shares = np.divide(
        sharpened_candidates,
        candidate_sums,
        out=np.zeros_like(sharpened_candidates),
        where=candidate_sums > 0,
    )
    distribution_overlap = np.minimum(candidate_shares, reference_share).sum(axis=1)

    traits = functional_traits(frame)
    reference_traits = traits.loc[reference_rows[0]].to_numpy(dtype=float)
    candidate_traits = traits.to_numpy(dtype=float)
    comparable = np.isfinite(candidate_traits) & np.isfinite(reference_traits)
    trait_weights = np.array([1.0, 1.2, 1.2, 1.1, 1.1, 0.7, 1.3])
    weighted_difference = np.where(
        comparable,
        np.abs(candidate_traits - reference_traits) * trait_weights,
        0,
    )
    comparable_weight = (comparable * trait_weights).sum(axis=1)
    mean_difference = np.divide(
        weighted_difference.sum(axis=1),
        comparable_weight,
        out=np.ones(len(frame)),
        where=comparable_weight > 0,
    )
    trait_similarity = np.clip(1 - mean_difference, 0, 1) ** 2
    # Affinity is evaluated across all attacking-role memberships, not a hard label.
    # Pure box 9s remain related to wide scorers/hybrids, but not interchangeable with them.
    attacking_affinity = np.array(
        [
            [1.0, 0.45, 0.35, 0.72, 0.3, 0.55],
            [0.45, 1.0, 0.86, 0.7, 0.62, 0.86],
            [0.35, 0.86, 1.0, 0.62, 0.86, 0.9],
            [0.72, 0.7, 0.62, 1.0, 0.72, 0.9],
            [0.3, 0.62, 0.86, 0.72, 1.0, 0.92],
            [0.55, 0.86, 0.9, 0.9, 0.92, 1.0],
        ]
    )
    reference_attacking = reference_share[:6]
    reference_attacking /= max(reference_attacking.sum(), 1e-9)
    candidate_attacking = candidate_shares[:, :6]
    candidate_attacking /= np.maximum(candidate_attacking.sum(axis=1, keepdims=True), 1e-9)
    subtype_affinity = (candidate_attacking @ attacking_affinity.T) @ reference_attacking
    compatibility = (
        0.1 * cosine
        + 0.2 * distribution_overlap
        + 0.4 * trait_similarity
        + 0.3 * subtype_affinity
    )
    reference_dominant = int(np.argmax(reference_vector))
    candidate_dominant = np.argmax(candidate_values, axis=1)
    scoring_wide_index = ROLE_KEYS.index("scoring_wide")
    creative_wide_index = ROLE_KEYS.index("creative_wide")
    wide_choice = np.where(
        candidate_values[:, scoring_wide_index]
        >= candidate_values[:, creative_wide_index],
        scoring_wide_index,
        creative_wide_index,
    )
    raw_width = pd.to_numeric(
        frame.get("pct_wide", pd.Series(np.nan, index=frame.index)), errors="coerce"
    ).to_numpy()
    raw_central = pd.to_numeric(
        frame.get("pct_central", pd.Series(np.nan, index=frame.index)), errors="coerce"
    ).to_numpy()
    lateral_spatial_evidence = np.isfinite(raw_width) & np.isfinite(raw_central)
    lateral_spatial_evidence &= raw_width >= raw_central + 0.12
    candidate_dominant = np.where(
        lateral_spatial_evidence, wide_choice, candidate_dominant
    )
    reference_dominant = int(candidate_dominant[reference_rows[0]])
    dominant_affinity = np.ones(len(frame))
    attacking_dominant = candidate_dominant < 6
    if reference_dominant < 6:
        dominant_affinity[attacking_dominant] = attacking_affinity[
            reference_dominant, candidate_dominant[attacking_dominant]
        ]
        # This is a soft mismatch penalty, not a hard single-role classification.
        # The full overlapping profile still determines the base compatibility above.
        compatibility *= 0.3 + 0.7 * dominant_affinity

    position_text = frame.get("positions", pd.Series("", index=frame.index)).fillna("").astype(str)
    position_text = position_text.str.casefold().str.replace("_", " ", regex=False)
    reference_attacking_share = reference_vector[:6].sum() / max(reference_vector.sum(), 1e-9)
    reference_defensive_share = reference_vector[7:].sum() / max(reference_vector.sum(), 1e-9)
    explicit_centre_back = position_text.str.contains(
        r"centre back|center back|\bcb\b", regex=True
    ).to_numpy()
    explicit_attacker = position_text.str.contains(
        r"striker|centre forward|center forward|wing|inside forward|\bst\b|\bcf\b|\blw\b|\brw\b",
        regex=True,
    ).to_numpy()
    explicit_centre_forward = position_text.str.contains(
        r"striker|centre forward|center forward|\bst\b|\bcf\b", regex=True
    ).to_numpy()
    explicit_wide_forward = position_text.str.contains(
        r"wing|inside forward|\blw\b|\brw\b", regex=True
    ).to_numpy()
    candidate_box_9 = candidate_dominant == ROLE_KEYS.index("box_9")
    if reference_dominant in {
        ROLE_KEYS.index("scoring_wide"),
        ROLE_KEYS.index("creative_wide"),
    }:
        compatibility = np.where(
            explicit_centre_forward & ~explicit_wide_forward & candidate_box_9,
            compatibility * 0.72,
            compatibility,
        )
        compatibility = np.where(
            explicit_wide_forward,
            np.minimum(compatibility * 1.12, 1.0),
            compatibility,
        )
    elif reference_dominant in {
        ROLE_KEYS.index("creative_10"),
        ROLE_KEYS.index("hybrid_creator_scorer"),
    }:
        compatibility = np.where(
            explicit_centre_forward & candidate_box_9,
            compatibility * 0.82,
            compatibility,
        )
    if reference_attacking_share >= 0.55:
        compatibility = np.where(explicit_centre_back, compatibility * 0.45, compatibility)
    if reference_defensive_share >= 0.55:
        compatibility = np.where(explicit_attacker, compatibility * 0.45, compatibility)

    output = frame.copy()
    output["Role compatibility"] = 100 * compatibility.clip(0, 1)
    output["Role family"] = [
        ROLE_LABELS[ROLE_KEYS[int(np.argmax(row))]] if np.max(row) > 0 else "Unclassified"
        for row in candidate_values
    ]
    output["Role confidence"] = np.divide(
        candidate_values.max(axis=1),
        candidate_values.sum(axis=1),
        out=np.zeros(len(frame)),
        where=candidate_values.sum(axis=1) > 0,
    )
    reference_max = reference_vector.max()
    return output, {
        ROLE_LABELS[key]: round(float(value / reference_max) * 100, 1)
        for key, value in zip(ROLE_KEYS, reference_vector, strict=True)
        if reference_max > 0 and value / reference_max >= 0.35
    }
