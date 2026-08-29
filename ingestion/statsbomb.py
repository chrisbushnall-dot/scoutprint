from __future__ import annotations

import json
import uuid
from pathlib import Path

import polars as pl

from ingestion.coordinates import statsbomb_to_canonical
from ingestion.zones import tactical_zone

NAMESPACE = uuid.UUID("34b038a1-85d7-45aa-b093-0d796cbcc1b7")


def canonical_id(entity: str, provider: str, provider_id: object) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{entity}:{provider}:{provider_id}"))


def _clock_minutes(value: str | None) -> float:
    if not value:
        return 0.0
    parts = value.split(":")
    try:
        return (
            int(parts[0]) + int(parts[1]) / 60 + (float(parts[2]) / 3600 if len(parts) > 2 else 0)
        )
    except (ValueError, IndexError):
        return 0.0


def normalize_statsbomb(
    data_dir: Path, competition_id: int, season_id: int, limit: int = 0
) -> dict[str, int]:
    provider = "statsbomb_open_data"
    raw = data_dir / "raw" / provider
    output = (
        data_dir / "normalized" / provider / f"competition={competition_id}" / f"season={season_id}"
    )
    output.mkdir(parents=True, exist_ok=True)
    competitions = json.loads((raw / "competitions.json").read_text())
    competition = next(
        c
        for c in competitions
        if c["competition_id"] == competition_id and c["season_id"] == season_id
    )
    matches = json.loads((raw / "matches" / str(competition_id) / f"{season_id}.json").read_text())
    if limit > 0:
        matches = matches[:limit]

    match_rows: list[dict] = []
    player_rows: dict[str, dict] = {}
    appearance_rows: list[dict] = []
    event_rows: list[dict] = []

    for match in matches:
        match_id = int(match["match_id"])
        canonical_match_id = canonical_id("match", provider, match_id)
        match_rows.append(
            {
                "match_id": canonical_match_id,
                "provider_match_id": str(match_id),
                "competition_id": canonical_id("competition", provider, competition_id),
                "competition_name": competition["competition_name"],
                "season_id": canonical_id("season", provider, season_id),
                "season_name": competition["season_name"],
                "match_date": match.get("match_date"),
                "home_team": match["home_team"]["home_team_name"],
                "away_team": match["away_team"]["away_team_name"],
                "source_provider": provider,
            }
        )
        lineups = json.loads((raw / "lineups" / f"{match_id}.json").read_text())
        for team in lineups:
            team_id = canonical_id("team", provider, team["team_id"])
            for player in team.get("lineup", []):
                provider_player_id = player["player_id"]
                player_id = canonical_id("player", provider, provider_player_id)
                player_rows[player_id] = {
                    "player_id": player_id,
                    "provider_player_id": str(provider_player_id),
                    "player_name": player["player_name"],
                    "nickname": player.get("player_nickname"),
                    "source_provider": provider,
                }
                positions = player.get("positions", [])
                minutes = sum(
                    max(0.0, _clock_minutes(p.get("to")) - _clock_minutes(p.get("from")))
                    for p in positions
                )
                appearance_rows.append(
                    {
                        "match_id": canonical_match_id,
                        "player_id": player_id,
                        "team_id": team_id,
                        "team_name": team["team_name"],
                        "minutes": min(minutes, 120.0),
                        "start": any(p.get("from") == "00:00" for p in positions),
                        "positions": ", ".join(
                            dict.fromkeys(
                                p.get("position", "") for p in positions if p.get("position")
                            )
                        ),
                        "source_provider": provider,
                    }
                )

        events = json.loads((raw / "events" / f"{match_id}.json").read_text())
        for event in events:
            if not event.get("player") or not event.get("location"):
                continue
            original_x, original_y = event["location"][:2]
            try:
                x, y = statsbomb_to_canonical(float(original_x), float(original_y))
            except (ValueError, TypeError):
                continue
            event_type = event["type"]["name"]
            subtype = "all_actions"
            if event_type == "Shot":
                subtype = "shots"
            elif event_type == "Pass":
                subtype = (
                    "chance_creation"
                    if event.get("pass", {}).get("shot_assist")
                    or event.get("pass", {}).get("goal_assist")
                    else "passes"
                )
            elif event_type == "Carry":
                subtype = "carries"
            elif event_type in {"Ball Receipt*", "Ball Receipt"}:
                subtype = "receipts"
            elif event_type in {
                "Pressure",
                "Duel",
                "Interception",
                "Ball Recovery",
                "Clearance",
                "Block",
                "50/50",
            }:
                subtype = "defensive_actions"
            zone = tactical_zone(x, y)
            player_id = canonical_id("player", provider, event["player"]["id"])
            event_rows.append(
                {
                    "event_id": canonical_id("event", provider, event["id"]),
                    "provider_event_id": event["id"],
                    "match_id": canonical_match_id,
                    "player_id": player_id,
                    "team_id": canonical_id("team", provider, event["team"]["id"]),
                    "event_type": event_type,
                    "fingerprint_type": subtype,
                    "period": event.get("period"),
                    "minute": event.get("minute"),
                    "second": event.get("second"),
                    "x_original": float(original_x),
                    "y_original": float(original_y),
                    "x": x,
                    "y": y,
                    "third": zone["third"],
                    "channel": zone["channel"],
                    "penalty_area": zone["penalty_area"],
                    "six_yard_box": zone["six_yard_box"],
                    "zone_14": zone["zone_14"],
                    "wide": zone["wide"],
                    "central": zone["central"],
                    "shot_xg": event.get("shot", {}).get("statsbomb_xg"),
                    "shot_outcome": event.get("shot", {}).get("outcome", {}).get("name"),
                    "pass_goal_assist": bool(event.get("pass", {}).get("goal_assist", False)),
                    "pass_shot_assist": bool(event.get("pass", {}).get("shot_assist", False)),
                    "source_provider": provider,
                    "source_path": f"events/{match_id}.json",
                }
            )

    frames = {
        "matches": pl.DataFrame(match_rows),
        "players": pl.DataFrame(list(player_rows.values())),
        "appearances": pl.DataFrame(appearance_rows),
        "events": pl.DataFrame(event_rows),
    }
    for name, frame in frames.items():
        frame.write_parquet(output / f"{name}.parquet", compression="zstd")
    return {name: frame.height for name, frame in frames.items()}
