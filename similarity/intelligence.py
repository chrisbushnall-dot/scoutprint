from __future__ import annotations

import json
import math
from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

from similarity.scope import is_excluded_product_competition

ROLE_TAXONOMY = (
    "Box 9",
    "Linking 9",
    "Channel Forward",
    "Inside Forward",
    "Wide Creator",
    "Touchline Winger",
    "Hybrid Scorer-Creator",
    "Second Striker",
    "Creative 10",
    "Progressive 8",
    "Box-to-Box 8",
    "Deep Progressor",
    "Controller",
    "Ball Winner",
    "Inverted Fullback",
    "Overlapping Fullback",
    "Progressive Centre-Back",
    "Stopper",
)

ROLE_GROUP = {
    **{role: "Attack" for role in ROLE_TAXONOMY[:9]},
    **{role: "Midfield" for role in ROLE_TAXONOMY[9:14]},
    **{role: "Defence" for role in ROLE_TAXONOMY[14:]},
    "Goalkeeper": "Goalkeeper",
    "Unclassified": "Unclassified",
}

TRAIT_METRICS = {
    "scoring": ("goals_p90", "xg_p90", "shots_p90"),
    "creation": ("assists_p90", "xa_p90", "chance_creation_p90"),
    "progression": ("progressions_p90", "carries_p90", "dribbles_p90"),
    "passing": ("passes_p90", "receipts_p90"),
    "defending": ("defensive_actions_p90", "pressures_p90"),
    "box": ("box_presence_rate", "pct_penalty_area"),
    "central": ("pct_central",),
    "width": ("pct_wide",),
    "half_space": ("pct_half_space",),
    "attacking_third": ("pct_attacking_third",),
}

ROLE_WEIGHTS = {
    "Box 9": {"scoring": 0.42, "box": 0.34, "central": 0.16},
    "Linking 9": {"creation": 0.28, "passing": 0.26, "box": 0.16, "scoring": 0.14},
    "Channel Forward": {"scoring": 0.30, "progression": 0.27, "width": 0.20, "box": 0.12},
    "Inside Forward": {"scoring": 0.34, "width": 0.25, "half_space": 0.20, "creation": 0.10},
    "Wide Creator": {"creation": 0.36, "width": 0.24, "progression": 0.20, "passing": 0.10},
    "Touchline Winger": {"width": 0.42, "progression": 0.26, "creation": 0.20},
    "Hybrid Scorer-Creator": {"scoring": 0.33, "creation": 0.33, "half_space": 0.14, "passing": 0.09},
    "Second Striker": {"scoring": 0.30, "creation": 0.25, "box": 0.20, "half_space": 0.14},
    "Creative 10": {"creation": 0.40, "passing": 0.22, "progression": 0.18, "half_space": 0.10},
    "Progressive 8": {"progression": 0.35, "passing": 0.25, "creation": 0.18, "defending": 0.10},
    "Box-to-Box 8": {"progression": 0.25, "defending": 0.25, "passing": 0.20, "scoring": 0.10},
    "Deep Progressor": {"progression": 0.30, "passing": 0.34, "defending": 0.15, "central": 0.10},
    "Controller": {"passing": 0.42, "central": 0.22, "progression": 0.18, "defending": 0.08},
    "Ball Winner": {"defending": 0.54, "passing": 0.18, "progression": 0.10, "central": 0.08},
    "Inverted Fullback": {"central": 0.25, "passing": 0.24, "progression": 0.22, "defending": 0.18},
    "Overlapping Fullback": {"width": 0.32, "progression": 0.27, "creation": 0.18, "defending": 0.14},
    "Progressive Centre-Back": {"passing": 0.30, "progression": 0.25, "defending": 0.25, "central": 0.12},
    "Stopper": {"defending": 0.56, "central": 0.22, "passing": 0.10},
}

ROLE_COMPONENTS = {
    role: tuple(
        metric
        for trait in weights
        for metric in TRAIT_METRICS[trait]
    )
    for role, weights in ROLE_WEIGHTS.items()
}

# Development is a season-on-season performance signal, not a playing-time signal.
# Both seasons need a meaningful sample before their role-relative rates can be compared.
DEVELOPMENT_MIN_MINUTES = 900
DEVELOPMENT_MIN_COMMON_METRICS = 2
DEVELOPMENT_MIN_COMMON_COVERAGE = 0.5


def _mean_available(frame: pd.DataFrame, columns: Iterable[str]) -> pd.Series:
    available = [column for column in columns if column in frame]
    if not available:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return frame[available].mean(axis=1, skipna=True)


def _safe_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_json(item) for item in value]
    if value is None:
        return None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return round(float(value), 3) if math.isfinite(float(value)) else None
    return value


def _json(value: Any) -> str:
    return json.dumps(_safe_json(value), ensure_ascii=False, separators=(",", ":"))


def _season_window(row: pd.Series) -> str | None:
    year = row.get("season_start_year")
    if pd.isna(year):
        return None
    year = int(year)
    if row.get("source_provider") == "american_soccer_analysis":
        return f"{year - 1}/{str(year)[-2:]}"
    return f"{year}/{str(year + 1)[-2:]}"


def _position_priors(position: str) -> dict[str, float]:
    text = str(position or "").casefold().replace("_", " ")
    priors = {role: 0.0 for role in ROLE_TAXONOMY}
    if any(token in text for token in ("goalkeeper", " gk")):
        return priors
    if any(token in text for token in ("striker", "centre forward", "center forward", " cf", " st")):
        for role in ("Box 9", "Linking 9", "Channel Forward", "Second Striker"):
            priors[role] = 0.10
    if any(token in text for token in ("wing", "wide", "left forward", "right forward", " lw", " rw")):
        for role in ("Inside Forward", "Wide Creator", "Touchline Winger", "Channel Forward"):
            priors[role] = 0.10
    if any(token in text for token in ("attacking midfield", "offensive midfield", " cam", " am")):
        for role in ("Creative 10", "Hybrid Scorer-Creator", "Second Striker"):
            priors[role] = 0.10
    if "midfield" in text or text.strip() in {"m", "cm", "dm"}:
        for role in ("Progressive 8", "Box-to-Box 8", "Deep Progressor", "Controller", "Ball Winner"):
            priors[role] = 0.08
    if any(token in text for token in ("fullback", "full back", "wingback", "wing back", "left back", "right back")):
        priors["Inverted Fullback"] = 0.11
        priors["Overlapping Fullback"] = 0.11
    if any(token in text for token in ("centre back", "center back", "central defender", " cb")):
        priors["Progressive Centre-Back"] = 0.12
        priors["Stopper"] = 0.12
    return priors


def _cosine_change(left: Any, right: Any) -> float | None:
    if not isinstance(left, (list, tuple, np.ndarray)) or not isinstance(
        right, (list, tuple, np.ndarray)
    ):
        return None
    a, b = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if a.size == 0 or a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        return None
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator <= 0:
        return None
    return round(100 * (1 - float(np.dot(a, b) / denominator)), 2)


def _confidence_score(row: pd.Series) -> float:
    minutes = float(row.get("minutes") or 0) if pd.notna(row.get("minutes")) else 0
    metric_coverage = float(row.get("metric_coverage") or 0)
    seasons = float(row.get("career_seasons") or 1)
    tier = {"A": 1.0, "B": 0.86, "C": 0.68}.get(str(row.get("data_tier")), 0.62)
    spatial = 1.0 if bool(row.get("spatial_available")) else 0.35
    value = (
        0.30 * min(math.sqrt(max(minutes, 0) / 1800), 1)
        + 0.25 * metric_coverage
        + 0.15 * min(seasons / 3, 1)
        + 0.20 * tier
        + 0.10 * spatial
    )
    return round(100 * value, 2)


def build_player_intelligence(history: pd.DataFrame) -> pd.DataFrame:
    """Precompute transparent player intelligence from canonical player-seasons.

    The function does no provider I/O. It consumes the current normalized/canonical history and
    emits one last-known-good friendly table for API reads.
    """

    frame = history.copy()
    if "is_primary_profile" in frame:
        frame = frame[frame["is_primary_profile"].fillna(False)].copy()
    if "competition_name" in frame:
        frame = frame[
            ~frame["competition_name"].map(is_excluded_product_competition)
        ].copy()
    frame = frame.drop_duplicates("player_season_id", keep="first").reset_index(drop=True)
    numeric = sorted(
        {
            metric
            for metrics in TRAIT_METRICS.values()
            for metric in metrics
        }
        | {"age", "minutes", "season_start_year", "comparison_coverage"}
    )
    for column in numeric:
        if column not in frame:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["canonical_person_id"] = frame.get("canonical_person_id", frame["canonical_player_id"])
    frame["canonical_person_id"] = frame["canonical_person_id"].fillna(frame["canonical_player_id"])
    frame["candidate_window"] = frame.apply(_season_window, axis=1)

    season_group = frame.groupby("season_start_year", dropna=False)
    percentile_columns: list[str] = []
    raw_metrics = sorted({metric for metrics in TRAIT_METRICS.values() for metric in metrics})
    for metric in raw_metrics:
        column = f"pct_{metric}"
        frame[column] = season_group[metric].rank(pct=True, method="average") * 100
        percentile_columns.append(column)
    for trait, metrics in TRAIT_METRICS.items():
        frame[f"trait_{trait}"] = _mean_available(
            frame, [f"pct_{metric}" for metric in metrics]
        ) / 100

    scores = pd.DataFrame(index=frame.index, columns=ROLE_TAXONOMY, dtype=float)
    for role, weights in ROLE_WEIGHTS.items():
        values = pd.DataFrame(
            {
                trait: frame[f"trait_{trait}"] * weight
                for trait, weight in weights.items()
            }
        )
        observed_weight = pd.DataFrame(
            {
                trait: frame[f"trait_{trait}"].notna().astype(float) * weight
                for trait, weight in weights.items()
            }
        ).sum(axis=1)
        scores[role] = values.sum(axis=1, skipna=True).div(observed_weight.where(observed_weight > 0))
    for index, position in frame["positions"].fillna("").items():
        if "goalkeeper" in str(position).casefold():
            scores.loc[index] = 0
            continue
        for role, prior in _position_priors(position).items():
            scores.at[index, role] = float(scores.at[index, role] or 0) + prior

    score_values = scores.fillna(0).to_numpy(dtype=float)
    order = np.argsort(-score_values, axis=1)
    top = score_values[np.arange(len(frame)), order[:, 0]]
    second = score_values[np.arange(len(frame)), order[:, 1]]
    role_array = np.asarray(ROLE_TAXONOMY, dtype=object)
    frame["primary_role"] = role_array[order[:, 0]]
    goalkeeper = frame["positions"].fillna("").str.contains("goalkeeper", case=False, regex=False)
    frame.loc[goalkeeper, "primary_role"] = "Goalkeeper"
    secondary = np.where((second >= top * 0.88) & (second > 0), role_array[order[:, 1]], None)
    frame["secondary_role"] = secondary
    frame.loc[goalkeeper, "secondary_role"] = None
    metric_observed = frame[raw_metrics].notna().sum(axis=1)
    frame["metric_coverage"] = metric_observed / len(raw_metrics)
    separation = np.divide(top - second, np.maximum(top, 1e-9))
    frame["role_confidence_score"] = np.clip(
        100 * (0.55 * separation + 0.45 * frame["metric_coverage"]), 0, 100
    ).round(2)
    frame["role_confidence"] = np.select(
        [frame["role_confidence_score"] >= 62, frame["role_confidence_score"] >= 40],
        ["HIGH", "MEDIUM"],
        default="LOW",
    )
    frame.loc[goalkeeper, ["role_confidence_score", "role_confidence"]] = [100, "HIGH"]
    no_behaviour = metric_observed.eq(0) & ~goalkeeper
    frame.loc[no_behaviour, "primary_role"] = "Unclassified"
    frame.loc[no_behaviour, "secondary_role"] = None
    frame.loc[no_behaviour, ["role_confidence_score", "role_confidence"]] = [0, "LOW"]

    def role_evidence(index: int) -> str:
        role = frame.at[index, "primary_role"]
        if role == "Goalkeeper":
            return _json({"position_support": "Goalkeeper", "dimensions": []})
        if role == "Unclassified":
            return _json(
                {
                    "position_support": frame.at[index, "positions"],
                    "dimensions": [],
                    "limitation": "No behavioural metrics available",
                }
            )
        weights = ROLE_WEIGHTS[role]
        evidence = sorted(
            (
                {
                    "dimension": trait.replace("_", " ").title(),
                    "percentile": 100 * float(frame.at[index, f"trait_{trait}"]),
                    "weight": weight,
                }
                for trait, weight in weights.items()
                if pd.notna(frame.at[index, f"trait_{trait}"])
            ),
            key=lambda item: item["percentile"] * item["weight"],
            reverse=True,
        )
        return _json({"position_support": frame.at[index, "positions"], "dimensions": evidence[:4]})

    frame["role_evidence_json"] = [role_evidence(index) for index in frame.index]

    # Current Level uses role-and-season-relative component percentiles, then exposes its
    # population and sample reliability adjustment rather than implying a league-strength model.
    frame["role_group"] = frame["primary_role"].map(ROLE_GROUP)
    component_values: list[dict[str, float | None]] = []
    role_percentiles: dict[str, pd.Series] = {}
    for metric in raw_metrics:
        role_percentiles[metric] = (
            frame.groupby(["season_start_year", "primary_role"], dropna=False)[metric]
            .rank(pct=True, method="average")
            * 100
        )
    for index, row in frame.iterrows():
        metrics = ROLE_COMPONENTS.get(row["primary_role"], ("passes_p90", "defensive_actions_p90"))
        unique_metrics = tuple(dict.fromkeys(metrics))
        component_values.append(
            {
                metric: (
                    float(role_percentiles[metric].at[index])
                    if metric in role_percentiles and pd.notna(role_percentiles[metric].at[index])
                    else None
                )
                for metric in unique_metrics
            }
        )
    frame["current_level_components_json"] = [_json(value) for value in component_values]
    frame["current_level_raw"] = [
        np.mean([value for value in components.values() if value is not None])
        if any(value is not None for value in components.values())
        else np.nan
        for components in component_values
    ]
    league_population = frame.groupby(
        ["competition_name", "season_start_year"], dropna=False
    )["player_season_id"].transform("size")
    frame["league_population"] = league_population.astype(int)
    frame["league_population_factor"] = np.clip(
        np.log10(np.maximum(league_population, 10)) / math.log10(250), 0.72, 1
    ).round(3)
    frame["sample_factor"] = np.clip(
        np.sqrt(frame["minutes"].fillna(0).clip(lower=0) / 1800), 0, 1
    ).round(3)
    frame["current_level"] = (
        frame["current_level_raw"]
        * (0.85 + 0.15 * frame["league_population_factor"])
        * (0.75 + 0.25 * frame["sample_factor"])
    ).round(2)

    frame["career_seasons"] = frame.groupby("canonical_person_id")["season_start_year"].transform(
        "nunique"
    )
    frame["confidence_score"] = frame.apply(_confidence_score, axis=1)
    frame["confidence_label"] = np.select(
        [frame["confidence_score"] >= 76, frame["confidence_score"] >= 56],
        ["HIGH", "MEDIUM"],
        default="LOW",
    )

    frame = frame.sort_values(
        ["canonical_person_id", "season_start_year", "source_preference_rank"],
        na_position="last",
    ).reset_index(drop=True)
    grouped = frame.groupby("canonical_person_id", sort=False)
    frame["previous_season_year"] = grouped["season_start_year"].shift(1)
    frame["previous_current_level"] = grouped["current_level"].shift(1)
    frame["previous_current_level_raw"] = grouped["current_level_raw"].shift(1)
    frame["previous_current_level_components_json"] = grouped[
        "current_level_components_json"
    ].shift(1)
    frame["previous_role"] = grouped["primary_role"].shift(1)
    frame["previous_role_group"] = grouped["role_group"].shift(1)
    frame["previous_team"] = grouped["team_name"].shift(1)
    frame["previous_league"] = grouped["competition_name"].shift(1)
    frame["previous_xg_p90"] = grouped["xg_p90"].shift(1)
    frame["previous_xa_p90"] = grouped["xa_p90"].shift(1)
    frame["previous_minutes"] = grouped["minutes"].shift(1)
    frame["previous_sample_factor"] = grouped["sample_factor"].shift(1)
    frame["previous_spatial"] = grouped["fp_all_actions"].shift(1)
    consecutive = frame["season_start_year"].eq(frame["previous_season_year"] + 1)
    comparable_role = frame["role_group"].eq(frame["previous_role_group"])
    sufficient_samples = frame["minutes"].ge(DEVELOPMENT_MIN_MINUTES) & frame[
        "previous_minutes"
    ].ge(DEVELOPMENT_MIN_MINUTES)
    base_comparable = consecutive & comparable_role & sufficient_samples

    def common_component_change(row: pd.Series) -> tuple[float, list[dict[str, float]], float]:
        if not bool(base_comparable.at[row.name]):
            return np.nan, [], 0.0
        current = json.loads(row["current_level_components_json"])
        previous = json.loads(row["previous_current_level_components_json"])
        current_available = {key: value for key, value in current.items() if value is not None}
        previous_available = {key: value for key, value in previous.items() if value is not None}
        common = sorted(current_available.keys() & previous_available.keys())
        denominator = max(len(current_available), len(previous_available), 1)
        coverage = len(common) / denominator
        if (
            len(common) < DEVELOPMENT_MIN_COMMON_METRICS
            or coverage < DEVELOPMENT_MIN_COMMON_COVERAGE
        ):
            return np.nan, [], coverage
        changes = [
            {
                "metric": metric,
                "previous": float(previous_available[metric]),
                "current": float(current_available[metric]),
                "change": float(current_available[metric] - previous_available[metric]),
            }
            for metric in common
        ]
        return float(np.mean([item["change"] for item in changes])), changes, coverage

    component_changes = frame.apply(common_component_change, axis=1)
    frame["development_raw"] = [item[0] for item in component_changes]
    frame["development_common_metrics_json"] = [_json(item[1]) for item in component_changes]
    frame["development_common_coverage"] = [item[2] for item in component_changes]
    # Compare only like-for-like role-component percentiles, excluding Current Level's minutes
    # adjustment, population-size adjustment, and any evidence available in just one season. Then
    # shrink the movement by the weaker sample reliability. This prevents a 168 -> 3,499 minute
    # change (or a change in available fields) from masquerading as player improvement.
    frame["development_reliability"] = pd.concat(
        [frame["sample_factor"], frame["previous_sample_factor"]], axis=1
    ).min(axis=1, skipna=False)
    frame["development"] = (
        frame["development_raw"] * frame["development_reliability"]
    ).round(2)
    frame["role_changed"] = (frame["primary_role"] != frame["previous_role"]).where(
        consecutive, False
    )
    frame["spatial_change"] = [
        _cosine_change(previous, current) if is_consecutive else None
        for previous, current, is_consecutive in zip(
            frame["previous_spatial"], frame["fp_all_actions"], consecutive, strict=True
        )
    ]
    frame["xg_change"] = (frame["xg_p90"] - frame["previous_xg_p90"]).where(consecutive).round(3)
    frame["xa_change"] = (frame["xa_p90"] - frame["previous_xa_p90"]).where(consecutive).round(3)
    frame["minutes_change"] = (frame["minutes"] - frame["previous_minutes"]).where(consecutive).round(0)

    def development_context(row: pd.Series) -> str | None:
        if pd.isna(row["previous_season_year"]):
            return None
        if not bool(consecutive.at[row.name]):
            return _json(
                {
                    "status": "unavailable",
                    "reason": "The prior record is not a consecutive season.",
                }
            )
        if not bool(comparable_role.at[row.name]):
            return _json(
                {
                    "status": "unavailable",
                    "reason": "The behavioural role group changed; use Role Changes instead.",
                    "from_role": row["previous_role"],
                }
            )
        if not bool(sufficient_samples.at[row.name]):
            return _json(
                {
                    "status": "unavailable",
                    "reason": (
                        f"At least {DEVELOPMENT_MIN_MINUTES:,} minutes are required in both "
                        "seasons for a Development comparison."
                    ),
                    "minimum_minutes_per_season": DEVELOPMENT_MIN_MINUTES,
                    "previous_minutes": row["previous_minutes"],
                    "current_minutes": row["minutes"],
                }
            )
        if pd.isna(row["development_raw"]):
            return _json(
                {
                    "status": "unavailable",
                    "reason": (
                        "The two seasons do not share enough like-for-like role-performance "
                        "metrics for a Development comparison."
                    ),
                    "minimum_common_metrics": DEVELOPMENT_MIN_COMMON_METRICS,
                    "minimum_common_coverage": DEVELOPMENT_MIN_COMMON_COVERAGE,
                    "common_coverage": row["development_common_coverage"],
                }
            )
        if pd.isna(row["development"]):
            return _json(
                {
                    "status": "unavailable",
                    "reason": "Comparable role-performance evidence is incomplete.",
                }
            )
        changes = {
            "xG/90": row["xg_change"],
            "xA/90": row["xa_change"],
            "Minutes": row["minutes_change"],
        }
        biggest = sorted(
            (
                {"metric": metric, "change": value}
                for metric, value in changes.items()
                if pd.notna(value)
            ),
            key=lambda item: abs(float(item["change"])),
            reverse=True,
        )
        return _json(
            {
                "status": "comparable",
                "method": (
                    "like-for-like role-component percentile change, "
                    "sample-reliability adjusted"
                ),
                "minimum_minutes_per_season": DEVELOPMENT_MIN_MINUTES,
                "previous_performance_percentile": row["previous_current_level_raw"],
                "current_performance_percentile": row["current_level_raw"],
                "sample_reliability": row["development_reliability"],
                "common_metric_coverage": row["development_common_coverage"],
                "common_metric_changes": json.loads(row["development_common_metrics_json"]),
                "biggest_metric_changes": biggest[:3],
                "team_change": row["previous_team"] != row["team_name"],
                "from_team": row["previous_team"],
                "league_change": row["previous_league"] != row["competition_name"],
                "from_league": row["previous_league"],
            }
        )

    frame["development_context_json"] = frame.apply(development_context, axis=1)
    goal_gap = frame["xg_p90"] - frame["goals_p90"]
    assist_gap = frame["xa_p90"] - frame["assists_p90"]
    frame["underlying_output_label"] = np.select(
        [goal_gap >= 0.15, assist_gap >= 0.10, goal_gap <= -0.15],
        ["Production Lag", "Ahead of Results", "Finishing Overperformance"],
        default="In Line",
    )
    frame.loc[frame[["xg_p90", "goals_p90", "xa_p90", "assists_p90"]].isna().all(axis=1), "underlying_output_label"] = "Unavailable"
    frame["output_gap"] = pd.concat([goal_gap, assist_gap], axis=1).max(
        axis=1, skipna=True
    )

    age_context = np.where(
        frame["age"].isna(),
        50,
        np.clip(100 - np.maximum(frame["age"] - 20, 0) * 5.5, 20, 100),
    )
    development_component = np.where(
        frame["development"].isna(), 50, np.clip(50 + frame["development"] * 2, 0, 100)
    )
    reliability = frame["sample_factor"] * 100
    role_output = frame["current_level_raw"].fillna(0)
    frame["radar_score"] = (
        0.40 * frame["current_level"].fillna(0)
        + 0.15 * development_component
        + 0.15 * age_context
        + 0.15 * role_output
        + 0.10 * reliability
        + 0.05 * frame["confidence_score"]
    ).round(2)
    frame["breakout_score"] = (
        0.72 * frame["radar_score"] + 0.18 * age_context + 0.10 * development_component
    ).round(2)
    frame["radar_components_json"] = [
        _json(
            {
                "current_level": current,
                "development_velocity": development,
                "age_context": age,
                "role_underlying_output": output,
                "minutes_reliability": reliable,
                "data_confidence": confidence,
            }
        )
        for current, development, age, output, reliable, confidence in zip(
            frame["current_level"],
            development_component,
            age_context,
            role_output,
            reliability,
            frame["confidence_score"],
            strict=True,
        )
    ]

    drop_columns = [
        *percentile_columns,
        *[f"trait_{trait}" for trait in TRAIT_METRICS],
        "previous_spatial",
    ]
    return frame.drop(columns=[column for column in drop_columns if column in frame])
