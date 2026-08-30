from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl


def _completed_seasons(data_dir: Path) -> set[tuple[str, str]] | None:
    queue_path = data_dir / "private/state/api_football_queue.parquet"
    smoke_path = data_dir / "private/state/api_football_smoke.parquet"
    if not queue_path.exists() and not smoke_path.exists():
        return None
    completed: set[tuple[str, str]] = set()
    if smoke_path.exists():
        for row in pl.read_parquet(smoke_path).select(
            "competition_name", "season_name"
        ).unique().iter_rows():
            completed.add((row[0], row[1]))
    if queue_path.exists():
        queue = pl.read_parquet(queue_path)
        for group in queue.partition_by(["competition", "season"], as_dict=False):
            statuses = set(group["status"].to_list())
            if statuses == {"complete"}:
                completed.add((group["competition"].item(0), str(group["season"].item(0))))
    return completed


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("%", ""))
    except (TypeError, ValueError):
        return None


def normalize_player_page(
    data_dir: Path,
    payload: dict[str, Any],
    *,
    league_id: int,
    season: int,
    page: int,
) -> Path:
    """Normalize one API-Football response page without inventing missing values."""
    rows: list[dict[str, Any]] = []
    for item in payload.get("response", []):
        player = item.get("player") or {}
        birth = player.get("birth") or {}
        for statistics in item.get("statistics") or []:
            league = statistics.get("league") or {}
            if int(league.get("id") or league_id) != league_id:
                continue
            games = statistics.get("games") or {}
            team = statistics.get("team") or {}
            goals = statistics.get("goals") or {}
            shots = statistics.get("shots") or {}
            passes = statistics.get("passes") or {}
            tackles = statistics.get("tackles") or {}
            duels = statistics.get("duels") or {}
            dribbles = statistics.get("dribbles") or {}
            rows.append(
                {
                    "source_provider": "api_football",
                    "player_id": str(player.get("id")),
                    "provider_player_id": str(player.get("id")),
                    "player_name": player.get("name"),
                    "birth_date": birth.get("date"),
                    "age": _number(player.get("age")),
                    "nationality": player.get("nationality"),
                    "height": player.get("height"),
                    "weight": player.get("weight"),
                    "positions": games.get("position"),
                    "team_id": str(team.get("id")) if team.get("id") is not None else None,
                    "team_name": team.get("name"),
                    "competition_name": league.get("name"),
                    "country": league.get("country"),
                    "season_name": str(league.get("season") or season),
                    "appearances": _number(games.get("appearences")),
                    "starts": _number(games.get("lineups")),
                    "minutes": _number(games.get("minutes")),
                    "goals": _number(goals.get("total")),
                    "assists": _number(goals.get("assists")),
                    "shots": _number(shots.get("total")),
                    "shots_on_target": _number(shots.get("on")),
                    "passes": _number(passes.get("total")),
                    "key_passes": _number(passes.get("key")),
                    "pass_accuracy": _number(passes.get("accuracy")),
                    "tackles": _number(tackles.get("total")),
                    "blocks": _number(tackles.get("blocks")),
                    "interceptions": _number(tackles.get("interceptions")),
                    "duels": _number(duels.get("total")),
                    "duels_won": _number(duels.get("won")),
                    "dribbles_attempted": _number(dribbles.get("attempts")),
                    "dribbles_completed": _number(dribbles.get("success")),
                    "provider_xg": None,
                    "provider_npxg": None,
                    "provider_xa": None,
                    "data_tier": "C",
                    "metadata_coverage": None,
                    "statistical_coverage": None,
                    "spatial_coverage": 0.0,
                }
            )
    destination = (
        data_dir
        / "private"
        / "normalized"
        / "api_football"
        / f"league={league_id}"
        / f"season={season}"
        / f"page={page}.parquet"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()
    frame.write_parquet(destination, compression="zstd")
    return destination


def build_provider_table(data_dir: Path) -> Path | None:
    pages = sorted((data_dir / "private" / "normalized" / "api_football").glob("**/page=*.parquet"))
    if not pages:
        return None
    frames: list[pl.DataFrame] = []
    for path in pages:
        frame = pl.read_parquet(path)
        if frame.width:
            frames.append(frame)
    if not frames:
        return None
    combined = pl.concat(frames, how="diagonal_relaxed").unique(
        ["player_id", "team_id", "competition_name", "season_name"], keep="last"
    )
    keys = ["source_provider", "player_id", "provider_player_id", "competition_name", "season_name"]
    numeric_metrics = [
        column
        for column in (
            "appearances",
            "starts",
            "minutes",
            "goals",
            "assists",
            "shots",
            "shots_on_target",
            "passes",
            "key_passes",
            "tackles",
            "blocks",
            "interceptions",
            "duels",
            "duels_won",
            "dribbles_attempted",
            "dribbles_completed",
        )
        if column in combined.columns
    ]
    combined = combined.group_by(keys).agg(
        *[
            pl.col(column).drop_nulls().first().alias(column)
            for column in (
                "player_name",
                "birth_date",
                "age",
                "nationality",
                "height",
                "weight",
                "positions",
                "country",
                "provider_xg",
                "provider_npxg",
                "provider_xa",
                "data_tier",
                "metadata_coverage",
                "statistical_coverage",
                "spatial_coverage",
            )
            if column in combined.columns
        ],
        pl.col("team_id").drop_nulls().unique().sort().str.join(" | ").alias("team_id"),
        pl.col("team_name").drop_nulls().unique().sort().str.join(" | ").alias("team_name"),
        *[
            pl.when(pl.col(column).count() > 0)
            .then(pl.col(column).sum())
            .otherwise(None)
            .alias(column)
            for column in numeric_metrics
        ],
        pl.when(pl.col("pass_accuracy").count() > 0)
        .then(pl.col("pass_accuracy").mean())
        .otherwise(None)
        .alias("pass_accuracy"),
    )
    completed = _completed_seasons(data_dir)
    if completed is None:
        combined = combined.with_columns(pl.lit(True).alias("acquisition_complete"))
    else:
        combined = combined.with_columns(
            pl.struct("competition_name", "season_name")
            .map_elements(
                lambda row: (row["competition_name"], row["season_name"]) in completed,
                return_dtype=pl.Boolean,
            )
            .alias("acquisition_complete")
        )
    output = data_dir / "private" / "recent" / "providers" / "api_football.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.write_parquet(output, compression="zstd")
    return output
