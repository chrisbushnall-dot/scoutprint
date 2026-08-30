from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from providers.apifootball import TARGET_LEAGUES as APIFOOTBALL_TARGET_LEAGUES
from providers.apifootball import TARGET_SEASONS as APIFOOTBALL_TARGET_SEASONS
from providers.sportmonks import FREE_LEAGUE_IDS


def _number(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("total") or value.get("value")
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("%", ""))
    except (TypeError, ValueError):
        return None


def _stable_name_id(provider: str, *values: Any) -> str:
    evidence = "|".join(str(value or "").strip().lower() for value in values)
    return hashlib.sha256(f"{provider}|{evidence}".encode()).hexdigest()[:32]


def _season_age(birth_date: str | None, season_name: str | None) -> float | None:
    if not birth_date or not season_name:
        return None
    try:
        born = date.fromisoformat(str(birth_date)[:10])
        end_year = int(str(season_name).split("/")[-1])
        end_year += 2000 if end_year < 100 else 0
        endpoint = date(end_year, 6, 30)
    except (TypeError, ValueError):
        return None
    return round((endpoint - born).days / 365.2425, 1)


def _write_provider(data_dir: Path, provider: str, rows: list[dict[str, Any]]) -> Path:
    output = data_dir / "private" / "recent" / "providers" / f"{provider}.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows, infer_schema_length=None).write_parquet(output, compression="zstd")
    return output


def normalize_bigballs(data_dir: Path) -> Path:
    raw_root = data_dir / "private" / "raw" / "bigballs" / "xg_leaders"
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for path in sorted(raw_root.glob("*/*/*.json")):
        payload = json.loads(path.read_text()).get("data") or {}
        league = payload.get("league") or {}
        season = str(payload.get("season") or path.parts[-2])
        for leader in payload.get("leaders") or []:
            key = (
                str(league.get("name") or league.get("id") or path.parts[-3]),
                season,
                str(leader.get("player_name") or ""),
                str(leader.get("team") or ""),
            )
            row = merged.setdefault(
                key,
                {
                    "source_provider": "bigballs",
                    "player_id": _stable_name_id("bigballs", *key),
                    "provider_player_id": None,
                    "player_name": leader.get("player_name"),
                    "birth_date": None,
                    "age": None,
                    "nationality": None,
                    "height_cm": None,
                    "positions": leader.get("position"),
                    "team_name": leader.get("team"),
                    "competition_name": key[0],
                    "season_name": season,
                    "data_tier": "C",
                    "spatial_coverage": 0.0,
                },
            )
            mappings = {
                "matches": "appearances",
                "minutes": "minutes",
                "goals": "goals",
                "assists": "assists",
                "xg": "provider_xg",
                "npxg": "provider_npxg",
                "xa": "provider_xa",
                "shots": "shots",
                "key_passes": "key_passes",
                "xg_chain": "provider_xg_chain",
                "xg_buildup": "provider_xg_buildup",
            }
            for source, target in mappings.items():
                incoming = _number(leader.get(source))
                if incoming is not None and row.get(target) not in (None, incoming):
                    raise ValueError(f"Conflicting Big Balls value for {key}: {target}")
                row[target] = incoming if incoming is not None else row.get(target)
    return _write_provider(data_dir, "bigballs", list(merged.values()))


def normalize_apifootball_com(data_dir: Path) -> Path:
    root = data_dir / "private" / "raw" / "apifootball_com"
    coverage = json.loads((root / "coverage" / "leagues.json").read_text())
    league_map = {
        str(item["league_id"]): item
        for item in coverage
        if item.get("league_name") in APIFOOTBALL_TARGET_LEAGUES
        and item.get("league_season") in APIFOOTBALL_TARGET_SEASONS
    }
    rows: list[dict[str, Any]] = []
    for league_id, league in league_map.items():
        path = root / "teams" / f"league={league_id}.json"
        if not path.exists():
            continue
        for team in json.loads(path.read_text()):
            for player in team.get("players") or []:
                rows.append(
                    {
                        "source_provider": "apifootball_com",
                        "player_id": str(player.get("player_key")),
                        "provider_player_id": str(player.get("player_key")),
                        "player_name": player.get("player_name"),
                        "birth_date": player.get("player_birthdate"),
                        "age": _number(player.get("player_age")),
                        "nationality": player.get("player_country"),
                        "positions": player.get("player_type"),
                        "team_name": team.get("team_name"),
                        "competition_name": league.get("league_name"),
                        "season_name": league.get("league_season"),
                        "appearances": _number(player.get("player_match_played")),
                        "starts": _number(player.get("player_match_started")),
                        "minutes": _number(player.get("player_minutes")),
                        "goals": _number(player.get("player_goals")),
                        "assists": _number(player.get("player_assists")),
                        "shots": _number(player.get("player_shots_total")),
                        "shots_on_target": _number(player.get("player_shots_on_target")),
                        "tackles": _number(player.get("player_tackles")),
                        "blocks": _number(player.get("player_blocks")),
                        "interceptions": _number(player.get("player_interceptions")),
                        "clearances": _number(player.get("player_clearances")),
                        "duels": _number(player.get("player_duels_total")),
                        "duels_won": _number(player.get("player_duels_won")),
                        "dribbles_attempted": _number(player.get("player_dribble_attempts")),
                        "dribbles_completed": _number(player.get("player_dribble_succ")),
                        "passes": _number(player.get("player_passes")),
                        "pass_accuracy": _number(player.get("player_passes_accuracy")),
                        "key_passes": _number(player.get("player_key_passes")),
                        "provider_xg": None,
                        "provider_npxg": None,
                        "provider_xa": None,
                        "data_tier": "C",
                        "spatial_coverage": 0.0,
                    }
                )
    return _write_provider(data_dir, "apifootball_com", rows)


SPORTMONKS_TYPES = {
    "APPEARANCES": "appearances",
    "LINEUPS": "starts",
    "MINUTES_PLAYED": "minutes",
    "GOALS": "goals",
    "ASSISTS": "assists",
    "SHOTS_TOTAL": "shots",
    "SHOTS_ON_TARGET": "shots_on_target",
    "PASSES": "passes",
    "ACCURATE_PASSES": "passes_completed",
    "KEY_PASSES": "key_passes",
    "TACKLES": "tackles",
    "INTERCEPTIONS": "interceptions",
    "BLOCKED_SHOTS": "blocks",
    "CLEARANCES": "clearances",
    "DUELS": "duels",
    "DUELS_WON": "duels_won",
    "DRIBBLES_ATTEMPTS": "dribbles_attempted",
    "SUCCESSFUL_DRIBBLES": "dribbles_completed",
}


def normalize_sportmonks(data_dir: Path) -> Path:
    root = data_dir / "private" / "raw" / "sportmonks"
    season_pages = sorted((root / "coverage" / "seasons").glob("page=*.json"))
    season_rows = [
        item for path in season_pages for item in json.loads(path.read_text()).get("data", [])
    ]
    seasons = {int(item["id"]): item for item in season_rows}
    rows: list[dict[str, Any]] = []
    for path in sorted((root / "squads").glob("season=*/team=*.json")):
        if path.name.endswith(".meta.json"):
            continue
        season_id = int(path.parent.name.split("=", 1)[1])
        season = seasons.get(season_id, {})
        team_id = int(path.stem.split("=", 1)[1])
        team_name = None
        for team_path in sorted((root / "teams" / f"season={season_id}").glob("page=*.json")):
            team_payload = json.loads(team_path.read_text())
            match = next(
                (item for item in team_payload.get("data", []) if int(item["id"]) == team_id),
                None,
            )
            if match:
                team_name = match.get("name")
                break
        payload = json.loads(path.read_text())
        for statistic in payload.get("data") or []:
            player = statistic.get("player") or {}
            base = {
                "source_provider": "sportmonks",
                "player_id": str(statistic.get("player_id") or player.get("id")),
                "provider_player_id": str(statistic.get("player_id") or player.get("id")),
                "player_name": player.get("display_name") or player.get("name"),
                "birth_date": player.get("date_of_birth"),
                "age": _season_age(player.get("date_of_birth"), season.get("name")),
                "nationality": (player.get("nationality") or {}).get("name"),
                "height_cm": _number(player.get("height")),
                "positions": (player.get("position") or {}).get("name"),
                "competition_name": FREE_LEAGUE_IDS.get(season.get("league_id")),
                "season_name": season.get("name"),
                "provider_xg": None,
                "provider_npxg": None,
                "provider_xa": None,
                "data_tier": "C",
                "spatial_coverage": 0.0,
            }
            row = {**base, "team_name": team_name}
            for detail in statistic.get("details") or []:
                type_info = detail.get("type") or {}
                target = SPORTMONKS_TYPES.get(type_info.get("developer_name"))
                if target:
                    row[target] = _number(detail.get("value"))
            if row.get("passes") and row.get("passes_completed") is not None:
                row["pass_accuracy"] = row["passes_completed"] / row["passes"] * 100
            rows.append(row)
    frame = pl.DataFrame(rows, infer_schema_length=None)
    keys = [
        "source_provider",
        "player_id",
        "provider_player_id",
        "competition_name",
        "season_name",
    ]
    metric_columns = sorted(
        {
            target
            for target in SPORTMONKS_TYPES.values()
            if target in frame.columns and target != "pass_accuracy"
        }
    )
    frame = frame.group_by(keys).agg(
        *[
            pl.col(column).drop_nulls().first().alias(column)
            for column in (
                "player_name",
                "birth_date",
                "age",
                "nationality",
                "height_cm",
                "positions",
                "provider_xg",
                "provider_npxg",
                "provider_xa",
                "data_tier",
            )
        ],
        pl.col("team_name").drop_nulls().unique().sort().str.join(" | ").alias("team_name"),
        pl.col("spatial_coverage").max(),
        *[
            pl.when(pl.col(column).count() > 0)
            .then(pl.col(column).sum())
            .otherwise(None)
            .alias(column)
            for column in metric_columns
        ],
    )
    if "passes" in frame.columns and "passes_completed" in frame.columns:
        frame = frame.with_columns(
            pl.when(pl.col("passes") > 0)
            .then(pl.col("passes_completed") / pl.col("passes") * 100)
            .otherwise(None)
            .alias("pass_accuracy")
        )
    output = data_dir / "private" / "recent" / "providers" / "sportmonks.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(output, compression="zstd")
    return output
