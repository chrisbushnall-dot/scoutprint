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


def _selected(events: pl.DataFrame, kind: str) -> pl.DataFrame:
    if kind == "all_actions":
        return events
    if kind in {"receipts", "carries"}:
        return events.head(0)
    if kind == "goals":
        return events.filter(pl.col("is_goal"))
    if kind == "shots":
        return events.filter(pl.col("is_shot"))
    if kind == "chance_creation":
        return events.filter(pl.col("pass_goal_assist") | pl.col("pass_shot_assist"))
    if kind == "passes":
        return events.filter(pl.col("is_pass"))
    return events.filter(pl.col("fingerprint_type") == kind)


def build_wyscout_player_seasons(data_dir: Path, grid: tuple[int, int] = (16, 12)) -> int:
    base = data_dir / "normalized" / "wyscout_public" / "competition=england" / "season=2017-2018"
    events, players = (
        pl.read_parquet(base / "events.parquet"),
        pl.read_parquet(base / "players.parquet"),
    )
    appearances, teams = (
        pl.read_parquet(base / "appearances.parquet"),
        pl.read_parquet(base / "teams.parquet"),
    )
    player_lookup = {r["player_id"]: r for r in players.iter_rows(named=True)}
    team_lookup = {r["team_id"]: r["team_name"] for r in teams.iter_rows(named=True)}
    summary = appearances.group_by("player_id").agg(
        pl.col("minutes").sum().alias("minutes"),
        pl.len().alias("appearances"),
        pl.col("start").sum().alias("starts"),
        pl.col("team_id").mode().first().alias("team_id"),
    )
    app_lookup = {r["player_id"]: r for r in summary.iter_rows(named=True)}
    rows: list[dict] = []
    for key, player_events in events.partition_by("player_id", as_dict=True).items():
        player_id = key[0] if isinstance(key, tuple) else key
        player, appearance = player_lookup.get(player_id), app_lookup.get(player_id)
        if not player or not appearance:
            continue
        minutes = float(appearance["minutes"] or 0)
        row = {
            "player_season_id": f"{player_id}:2017-2018:england",
            "player_id": player_id,
            "player_name": player["player_name"],
            "competition_name": "Premier League",
            "season_name": "2017/18",
            "team_name": team_lookup.get(appearance["team_id"], "Unknown"),
            "positions": player.get("position"),
            "age": player.get("age_at_season_end"),
            "nationality": player.get("nationality"),
            "preferred_foot": player.get("preferred_foot"),
            "height_cm": player.get("height_cm"),
            "minutes": minutes,
            "appearances": int(appearance["appearances"]),
            "starts": int(appearance["starts"]),
            "grid_x": grid[0],
            "grid_y": grid[1],
            "source_provider": "wyscout_public",
            "spatial_available": True,
            "carries_available": False,
            "receipts_available": False,
            "xg_available": False,
        }
        for kind in FINGERPRINT_TYPES:
            selected = _selected(player_events, kind)
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
                "goals": int(player_events["is_goal"].sum()),
                "assists": int(player_events["pass_goal_assist"].sum()),
                "xg": None,
            }
        )
        row["goals_p90"] = per90(row["goals"], minutes)
        row["assists_p90"] = per90(row["assists"], minutes)
        row["xg_p90"] = None
        for kind in ("shots", "chance_creation", "passes", "defensive_actions"):
            row[f"{kind}_p90"] = per90(row[f"count_{kind}"], minutes)
        row["carries_p90"], row["receipts_p90"] = None, None
        rows.append(row)
    output = data_dir / "derived" / "player_seasons_wyscout_england_2017-2018.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(output, compression="zstd")
    return len(rows)
