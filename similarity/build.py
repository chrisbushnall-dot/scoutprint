from __future__ import annotations

from pathlib import Path

import polars as pl

from similarity.metrics import per90
from similarity.spatial import probability_grid

FINGERPRINT_TYPES = (
    "all_actions",
    "receipts",
    "shots",
    "goals",
    "chance_creation",
    "passes",
    "carries",
    "defensive_actions",
)


def _event_filter(frame: pl.DataFrame, kind: str) -> pl.DataFrame:
    if kind == "all_actions":
        return frame
    if kind == "goals":
        return frame.filter((pl.col("event_type") == "Shot") & (pl.col("shot_outcome") == "Goal"))
    if kind == "chance_creation":
        return frame.filter(pl.col("pass_shot_assist") | pl.col("pass_goal_assist"))
    if kind == "passes":
        return frame.filter(pl.col("event_type") == "Pass")
    return frame.filter(pl.col("fingerprint_type") == kind)


def build_player_seasons(
    data_dir: Path, competition_id: int, season_id: int, grid: tuple[int, int] = (16, 12)
) -> int:
    base = (
        data_dir
        / "normalized"
        / "statsbomb_open_data"
        / f"competition={competition_id}"
        / f"season={season_id}"
    )
    events = pl.read_parquet(base / "events.parquet")
    players = pl.read_parquet(base / "players.parquet")
    appearances = pl.read_parquet(base / "appearances.parquet")
    matches = pl.read_parquet(base / "matches.parquet")
    summary = appearances.group_by("player_id").agg(
        pl.col("minutes").sum().alias("minutes"),
        pl.len().alias("appearances"),
        pl.col("start").sum().alias("starts"),
        pl.col("team_name").mode().first().alias("team_name"),
        pl.col("positions").drop_nulls().mode().first().alias("positions"),
    )
    player_lookup = {row["player_id"]: row for row in players.iter_rows(named=True)}
    appearance_lookup = {row["player_id"]: row for row in summary.iter_rows(named=True)}
    meta = matches.row(0, named=True)
    rows: list[dict] = []
    for key, player_events in events.partition_by("player_id", as_dict=True).items():
        player_id = key[0] if isinstance(key, tuple) else key
        appearance, player = appearance_lookup.get(player_id), player_lookup.get(player_id)
        if not appearance or not player:
            continue
        minutes = float(appearance["minutes"] or 0)
        row = {
            "player_season_id": f"{player_id}:{meta['season_id']}:{meta['competition_id']}",
            "player_id": player_id,
            "player_name": player["player_name"],
            "competition_id": meta["competition_id"],
            "competition_name": meta["competition_name"],
            "season_id": meta["season_id"],
            "season_name": meta["season_name"],
            "team_name": appearance["team_name"],
            "positions": appearance["positions"],
            "minutes": minutes,
            "appearances": int(appearance["appearances"]),
            "starts": int(appearance["starts"]),
            "grid_x": grid[0],
            "grid_y": grid[1],
            "source_provider": "statsbomb_open_data",
        }
        for kind in FINGERPRINT_TYPES:
            selected = _event_filter(player_events, kind)
            row[f"fp_{kind}"] = (
                probability_grid(selected.select("x", "y").to_numpy(), grid).ravel().tolist()
            )
            row[f"count_{kind}"] = selected.height
        attacking = player_events.filter(pl.col("third") == "attacking_third")
        all_count, attacking_count = max(player_events.height, 1), max(attacking.height, 1)
        row.update(
            {
                "pct_attacking_third": attacking.height / all_count,
                "pct_penalty_area": player_events["penalty_area"].sum() / all_count,
                "pct_half_space": player_events.filter(
                    pl.col("channel").str.contains("half_space")
                ).height
                / all_count,
                "pct_central": player_events["central"].sum() / all_count,
                "pct_wide": player_events["wide"].sum() / all_count,
                "box_presence_rate": attacking["penalty_area"].sum() / attacking_count,
                "goals": player_events.filter(
                    (pl.col("event_type") == "Shot") & (pl.col("shot_outcome") == "Goal")
                ).height,
                "xg": float(player_events["shot_xg"].fill_null(0).sum()),
                "assists": int(player_events["pass_goal_assist"].sum()),
            }
        )
        for metric in ("goals", "xg", "assists"):
            row[f"{metric}_p90"] = per90(row[metric], minutes)
        for kind in (
            "shots",
            "chance_creation",
            "passes",
            "carries",
            "defensive_actions",
            "receipts",
        ):
            row[f"{kind}_p90"] = per90(row[f"count_{kind}"], minutes)
        rows.append(row)
    output = data_dir / "derived" / f"player_seasons_c{competition_id}_s{season_id}.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(output, compression="zstd")
    return len(rows)
