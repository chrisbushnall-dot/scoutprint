from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from providers.asa import TARGET_LEAGUES, TARGET_SEASONS


def _age_at_season_end(birth_date: str | None, season: int) -> float | None:
    if not birth_date:
        return None
    try:
        born = date.fromisoformat(birth_date[:10])
    except ValueError:
        return None
    endpoint = date(season, 12, 31)
    return round((endpoint - born).days / 365.2425, 1)


def _read(path: Path) -> pl.DataFrame:
    return pl.read_parquet(path)


def normalize_asa(data_dir: Path) -> dict[str, int]:
    root = data_dir / "private" / "raw" / "american_soccer_analysis"
    rows: list[pl.DataFrame] = []
    for league, competition in TARGET_LEAGUES.items():
        players = (
            _read(root / f"entities/{league}_players.parquet")
            .select(
                pl.col("player_id").cast(pl.String),
                pl.col("player_name").cast(pl.String),
                pl.col("birth_date").cast(pl.String, strict=False),
                pl.col("nationality").cast(pl.String, strict=False),
                pl.col("height_ft").cast(pl.Float64, strict=False),
                pl.col("height_in").cast(pl.Float64, strict=False),
            )
            .unique("player_id", keep="first")
        )
        teams = (
            _read(root / f"entities/{league}_teams.parquet")
            .select(pl.col("team_id").cast(pl.String), pl.col("team_name").cast(pl.String))
            .unique("team_id", keep="first")
        )
        for season in TARGET_SEASONS:
            xg = _read(root / f"stats/{league}/{season}_xgoals.parquet")
            xpass = _read(root / f"stats/{league}/{season}_xpass.parquet")
            goals_added = _read(root / f"stats/{league}/{season}_goals_added.parquet")
            expanded: list[dict[str, Any]] = []
            for row in goals_added.iter_rows(named=True):
                base = {key: row.get(key) for key in ("player_id", "team_id", "season_name")}
                for item in row.get("data") or []:
                    action = str(item.get("action_type", "unknown")).lower().replace(" ", "_")
                    base[f"ga_{action}"] = item.get("goals_added_raw")
                    base[f"actions_{action}"] = item.get("count_actions")
                expanded.append(base)
            ga = pl.DataFrame(expanded, infer_schema_length=None) if expanded else pl.DataFrame()
            keys = ["player_id", "team_id", "season_name"]
            frame = xg.join(xpass, on=keys, how="full", coalesce=True, suffix="_xpass")
            if ga.height:
                frame = frame.join(ga, on=keys, how="left")
            frame = frame.join(players, on="player_id", how="left").join(
                teams, on="team_id", how="left"
            )
            for column in (
                "ga_dribbling",
                "ga_passing",
                "ga_receiving",
                "ga_shooting",
                "ga_interrupting",
                "actions_dribbling",
                "actions_passing",
                "actions_receiving",
                "actions_shooting",
                "actions_interrupting",
            ):
                if column not in frame.columns:
                    frame = frame.with_columns(pl.lit(None, dtype=pl.Float64).alias(column))
            frame = (
                frame.group_by("player_id")
                .agg(
                    pl.col("player_name").drop_nulls().first(),
                    pl.col("birth_date").drop_nulls().first(),
                    pl.col("nationality").drop_nulls().first(),
                    pl.col("height_ft").drop_nulls().first(),
                    pl.col("height_in").drop_nulls().first(),
                    pl.col("general_position")
                    .drop_nulls()
                    .unique()
                    .sort()
                    .str.join(" | ")
                    .alias("positions"),
                    pl.col("team_name").drop_nulls().unique().sort().str.join(" | "),
                    pl.max_horizontal("minutes_played", "minutes_played_xpass")
                    .sum()
                    .alias("minutes"),
                    pl.col("count_games").sum().alias("appearances"),
                    pl.col("goals").sum(),
                    pl.col("primary_assists").sum().alias("assists"),
                    pl.col("xgoals").sum().alias("provider_xg"),
                    pl.col("xassists").sum().alias("provider_xa"),
                    pl.col("shots").sum(),
                    pl.col("shots_on_target").sum(),
                    pl.col("key_passes").sum(),
                    pl.col("attempted_passes").sum().alias("passes"),
                    (
                        (pl.col("attempted_passes") * pl.col("pass_completion_percentage")).sum()
                        / pl.col("attempted_passes").sum()
                    ).alias("pass_accuracy"),
                    *[
                        pl.col(column).sum().alias(column)
                        for column in frame.columns
                        if column.startswith(("ga_", "actions_"))
                    ],
                )
                .with_columns(
                    pl.lit("american_soccer_analysis").alias("source_provider"),
                    pl.col("player_id").alias("provider_player_id"),
                    pl.lit(competition).alias("competition_name"),
                    pl.lit(str(season)).alias("season_name"),
                    pl.lit(None, dtype=pl.Float64).alias("provider_npxg"),
                    pl.lit(None, dtype=pl.Float64).alias("starts"),
                    pl.lit(None, dtype=pl.Float64).alias("tackles"),
                    pl.lit(None, dtype=pl.Float64).alias("interceptions"),
                    pl.lit(None, dtype=pl.Float64).alias("blocks"),
                    pl.lit(None, dtype=pl.Float64).alias("duels"),
                    pl.lit(None, dtype=pl.List(pl.Float64)).alias("shot_spatial_vector"),
                    pl.lit(None, dtype=pl.List(pl.Float64)).alias("event_spatial_vector"),
                    pl.lit("C").alias("data_tier"),
                    pl.struct("birth_date")
                    .map_elements(
                        lambda row, season=season: _age_at_season_end(row["birth_date"], season),
                        return_dtype=pl.Float64,
                    )
                    .alias("age"),
                )
            )
            frame = frame.with_columns(
                ((pl.col("height_ft") * 12 + pl.col("height_in")) * 2.54).alias("height_cm"),
                pl.mean_horizontal(
                    pl.col("birth_date").is_not_null().cast(pl.Float64),
                    pl.col("nationality").is_not_null().cast(pl.Float64),
                    pl.col("positions").is_not_null().cast(pl.Float64),
                    pl.col("team_name").is_not_null().cast(pl.Float64),
                ).alias("metadata_coverage"),
                pl.mean_horizontal(
                    *[
                        pl.col(column).is_not_null().cast(pl.Float64)
                        for column in (
                            "minutes",
                            "goals",
                            "assists",
                            "provider_xg",
                            "provider_xa",
                            "shots",
                            "shots_on_target",
                            "key_passes",
                            "passes",
                            "pass_accuracy",
                        )
                    ]
                ).alias("statistical_coverage"),
                pl.lit(0.0).alias("spatial_coverage"),
            ).with_columns(
                (pl.col("goals") / pl.col("minutes") * 90).alias("goals_p90"),
                (pl.col("provider_xg") / pl.col("minutes") * 90).alias("xg_p90"),
                (pl.col("assists") / pl.col("minutes") * 90).alias("assists_p90"),
                (pl.col("provider_xa") / pl.col("minutes") * 90).alias("xa_p90"),
                (pl.col("shots") / pl.col("minutes") * 90).alias("shots_p90"),
                (pl.col("key_passes") / pl.col("minutes") * 90).alias("chance_creation_p90"),
                (pl.col("passes") / pl.col("minutes") * 90).alias("passes_p90"),
                pl.lit(None, dtype=pl.Float64).alias("carries_p90"),
                pl.lit(None, dtype=pl.Float64).alias("progressions_p90"),
                (pl.col("actions_interrupting") / pl.col("minutes") * 90).alias(
                    "defensive_actions_p90"
                ),
                pl.lit(None, dtype=pl.List(pl.Float64)).alias("fp_all_actions"),
            )
            rows.append(frame)
    output = data_dir / "private" / "recent" / "providers" / "american_soccer_analysis.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    combined = pl.concat(rows, how="diagonal_relaxed").sort(
        "competition_name", "season_name", "player_name"
    )
    combined.write_parquet(output, compression="zstd")
    return {
        "player_seasons": combined.height,
        "unique_players": combined["player_id"].n_unique(),
        "competitions": combined["competition_name"].n_unique(),
        "seasons": combined["season_name"].n_unique(),
    }


def build_recent_player_seasons(data_dir: Path) -> dict[str, int]:
    provider_paths = sorted((data_dir / "private" / "recent" / "providers").glob("*.parquet"))
    if not provider_paths:
        raise RuntimeError("No normalized recent provider tables were found")
    frames = [pl.read_parquet(path) for path in provider_paths]
    history_path = data_dir / "private/canonical_identity/player_season_history.parquet"
    if history_path.exists():
        established = pl.read_parquet(history_path).filter(
            pl.col("source_provider").is_in(["impect", "statsbomb_open_data", "afriskaut"])
            & pl.col("season_start_year").is_in([2023, 2024, 2025])
            & pl.col("is_primary_profile")
        )
        if established.height:
            for column in ("canonical_player_id", "provider_coverage"):
                if column in established.columns:
                    established = established.drop(column)
            established = established.with_columns(
                pl.lit("A").alias("data_tier"),
                pl.lit(True).alias("acquisition_complete"),
            )
            frames.append(established)
    providers = pl.concat(frames, how="diagonal_relaxed")
    if "acquisition_complete" in providers.columns:
        providers = providers.filter(
            (pl.col("source_provider") != "api_football")
            | pl.col("acquisition_complete").fill_null(False)
        )
    links_path = data_dir / "private" / "canonical_identity" / "player_identity_links.parquet"
    if links_path.exists():
        links = pl.read_parquet(links_path).select(
            "source_provider", "player_id", "canonical_player_id"
        )
        providers = providers.join(links, on=["source_provider", "player_id"], how="left")
    if "canonical_player_id" not in providers.columns:
        providers = providers.with_columns(
            pl.lit(None, dtype=pl.String).alias("canonical_player_id")
        )
    providers = providers.with_columns(
        pl.col("canonical_player_id").fill_null(
            pl.col("source_provider") + pl.lit(":") + pl.col("player_id")
        )
    )
    provider_rank = {
        "impect": 0,
        "statsbomb_open_data": 0,
        "afriskaut": 0,
        "american_soccer_analysis": 1,
        "sportmonks": 2,
        "api_football": 3,
        "bigballs": 4,
    }

    def season_key(provider: str, value: str) -> str:
        if provider in {"american_soccer_analysis", "afriskaut", "statsbomb_open_data"}:
            return value
        if "/" in value:
            start, end = value.split("/", 1)
            return f"{start}/{end[-2:]}"
        try:
            year = int(value)
        except ValueError:
            return value
        return f"{year}/{str(year + 1)[-2:]}" if year in (2023, 2024, 2025) else value

    def competition_key(value: str) -> str:
        return "Premier League" if value == "EPL" else value

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in providers.to_dicts():
        key = (
            row["canonical_player_id"],
            competition_key(str(row.get("competition_name") or "")),
            season_key(row["source_provider"], str(row.get("season_name") or "")),
        )
        grouped.setdefault(key, []).append(row)

    merged_rows: list[dict[str, Any]] = []
    for (canonical_player_id, competition, season), source_rows in grouped.items():
        source_rows.sort(key=lambda row: provider_rank.get(row["source_provider"], 99))
        merged = dict(source_rows[0])
        merged["canonical_player_id"] = canonical_player_id
        merged["competition_name"] = competition
        merged["season_name"] = season
        for row in source_rows[1:]:
            for column, value in row.items():
                if merged.get(column) is None and value is not None:
                    merged[column] = value
        merged["provider_coverage"] = sorted(
            {row["source_provider"] for row in source_rows}
        )
        merged["trajectory_coverage"] = 0.0
        merged["source_native_records_json"] = json.dumps(
            [
                {
                    key: value
                    for key, value in row.items()
                    if key
                    not in {
                        "canonical_player_id",
                        "provider_coverage",
                        "metric_provenance_json",
                        "source_native_records_json",
                    }
                }
                for row in source_rows
            ],
            default=str,
            sort_keys=True,
        )
        merged["metric_provenance_json"] = json.dumps(
            {
                "selection": "provider precedence; first non-null; no averaging",
                "provider_order": merged["provider_coverage"],
            },
            sort_keys=True,
        )
        merged_rows.append(merged)
    providers = pl.DataFrame(merged_rows, infer_schema_length=None)
    providers = providers.with_columns(
        pl.struct("canonical_player_id", "competition_name", "season_name")
        .map_elements(
            lambda row: "recent_player_season:"
            + hashlib.sha256(
                "|".join(
                    [
                        str(row["canonical_player_id"]),
                        str(row["competition_name"]),
                        str(row["season_name"]),
                    ]
                ).encode("utf-8")
            ).hexdigest()[:24],
            return_dtype=pl.String,
        )
        .alias("player_season_id")
    )
    output = data_dir / "private" / "canonical" / "recent_player_seasons.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    providers.write_parquet(output, compression="zstd")
    return {
        "player_seasons": providers.height,
        "canonical_players": providers["canonical_player_id"].n_unique(),
        "tier_a": providers.filter(pl.col("data_tier") == "A").height,
        "tier_b": providers.filter(pl.col("data_tier") == "B").height,
        "tier_c": providers.filter(pl.col("data_tier") == "C").height,
    }
