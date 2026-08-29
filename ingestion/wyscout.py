from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import polars as pl

from ingestion.statsbomb import canonical_id
from ingestion.zones import tactical_zone

PROVIDER = "wyscout_public"
GOAL_TAG, ASSIST_TAG, KEY_PASS_TAG = 101, 301, 302


def _full_name(player: dict) -> str:
    parts = [player.get("firstName", ""), player.get("middleName", ""), player.get("lastName", "")]
    return " ".join(part.strip() for part in parts if part and part.strip()) or player.get(
        "shortName", "Unknown"
    )


def _appearance_rows(match: dict) -> list[dict]:
    rows: list[dict] = []
    match_id = canonical_id("match", PROVIDER, match["wyId"])
    for provider_team_id, team_data in match.get("teamsData", {}).items():
        formation = team_data.get("formation", {}) or {}
        substitutions = formation.get("substitutions", []) or []
        # Five published team formations encode JSON null as the string "null".
        if not isinstance(substitutions, list):
            substitutions = []
        sub_out = {int(s["playerOut"]): min(float(s.get("minute", 90)), 90) for s in substitutions}
        sub_in = {int(s["playerIn"]): min(float(s.get("minute", 0)), 90) for s in substitutions}
        for item in formation.get("lineup", []) or []:
            player_id = int(item["playerId"])
            rows.append(
                {
                    "match_id": match_id,
                    "player_id": canonical_id("player", PROVIDER, player_id),
                    "team_id": canonical_id("team", PROVIDER, provider_team_id),
                    "minutes": max(0.0, sub_out.get(player_id, 90.0)),
                    "start": True,
                    "position_code": item.get("ownGoals", 0) and None,
                    "source_provider": PROVIDER,
                }
            )
        for item in formation.get("bench", []) or []:
            player_id = int(item["playerId"])
            if player_id not in sub_in:
                continue
            rows.append(
                {
                    "match_id": match_id,
                    "player_id": canonical_id("player", PROVIDER, player_id),
                    "team_id": canonical_id("team", PROVIDER, provider_team_id),
                    "minutes": max(0.0, 90.0 - sub_in[player_id]),
                    "start": False,
                    "position_code": None,
                    "source_provider": PROVIDER,
                }
            )
    return rows


def normalize_wyscout(
    data_dir: Path, competition: str = "England", limit: int = 0
) -> dict[str, int]:
    raw = data_dir / "raw" / PROVIDER
    output = data_dir / "normalized" / PROVIDER / "competition=england" / "season=2017-2018"
    output.mkdir(parents=True, exist_ok=True)
    players_raw = json.loads((raw / "players.json").read_text())
    teams_raw = json.loads((raw / "teams.json").read_text())
    matches_raw = json.loads((raw / f"matches_{competition}.json").read_text())
    events_raw = json.loads((raw / f"events_{competition}.json").read_text())
    if limit > 0:
        matches_raw = matches_raw[:limit]
        match_ids = {int(match["wyId"]) for match in matches_raw}
        events_raw = [event for event in events_raw if int(event["matchId"]) in match_ids]
    team_names = {int(team["wyId"]): team["name"] for team in teams_raw}
    player_lookup = {int(player["wyId"]): player for player in players_raw}
    used_player_ids = {
        int(event["playerId"]) for event in events_raw if int(event.get("playerId", 0))
    }
    match_rows, appearance_rows, event_rows = [], [], []
    seen_event_ids: set[int] = set()
    for match in matches_raw:
        teams_data = match.get("teamsData", {})
        home_id = next(
            (team_id for team_id, details in teams_data.items() if details.get("side") == "home"),
            None,
        )
        away_id = next(
            (team_id for team_id, details in teams_data.items() if details.get("side") == "away"),
            None,
        )
        match_rows.append(
            {
                "match_id": canonical_id("match", PROVIDER, match["wyId"]),
                "provider_match_id": str(match["wyId"]),
                "competition_id": canonical_id("competition", PROVIDER, "england"),
                "competition_name": "Premier League",
                "season_id": canonical_id("season", PROVIDER, "2017-2018"),
                "season_name": "2017/18",
                "match_date": str(match.get("dateutc", ""))[:10],
                "home_team": team_names.get(int(home_id), home_id) if home_id else None,
                "away_team": team_names.get(int(away_id), away_id) if away_id else None,
                "source_provider": PROVIDER,
            }
        )
        appearance_rows.extend(_appearance_rows(match))
    for event in events_raw:
        provider_event_id = int(event["id"])
        if provider_event_id in seen_event_ids:
            continue
        seen_event_ids.add(provider_event_id)
        positions = event.get("positions") or []
        player_id = int(event.get("playerId", 0))
        if not positions or not player_id:
            continue
        original_x, original_y = float(positions[0]["x"]), float(positions[0]["y"])
        if not (0 <= original_x <= 100 and 0 <= original_y <= 100):
            continue
        # Wyscout public event positions are expressed in the acting team's attacking frame.
        x, y = original_x, original_y
        tags = {int(tag["id"]) for tag in event.get("tags", [])}
        event_name, subevent = event.get("eventName", ""), event.get("subEventName", "")
        is_shot = event_name == "Shot" or subevent in {"Free kick shot", "Penalty"}
        is_pass = event_name == "Pass"
        defensive = event_name == "Duel" or subevent in {
            "Interception",
            "Clearance",
            "Ground defensive duel",
            "Air duel",
        }
        kind = (
            "shots"
            if is_shot
            else "chance_creation"
            if tags & {ASSIST_TAG, KEY_PASS_TAG}
            else "passes"
            if is_pass
            else "defensive_actions"
            if defensive
            else "all_actions"
        )
        zone = tactical_zone(x, y)
        event_rows.append(
            {
                "event_id": canonical_id("event", PROVIDER, provider_event_id),
                "provider_event_id": str(provider_event_id),
                "match_id": canonical_id("match", PROVIDER, event["matchId"]),
                "player_id": canonical_id("player", PROVIDER, player_id),
                "team_id": canonical_id("team", PROVIDER, event["teamId"]),
                "event_type": event_name,
                "event_subtype": subevent,
                "fingerprint_type": kind,
                "period": event.get("matchPeriod"),
                "event_seconds": event.get("eventSec"),
                "x_original": original_x,
                "y_original": original_y,
                "x": x,
                "y": y,
                "third": zone["third"],
                "channel": zone["channel"],
                "penalty_area": zone["penalty_area"],
                "six_yard_box": zone["six_yard_box"],
                "zone_14": zone["zone_14"],
                "wide": zone["wide"],
                "central": zone["central"],
                "is_shot": is_shot,
                "is_goal": GOAL_TAG in tags,
                "is_pass": is_pass,
                "pass_goal_assist": ASSIST_TAG in tags,
                "pass_shot_assist": KEY_PASS_TAG in tags,
                "shot_xg": None,
                "shot_outcome": "Goal" if GOAL_TAG in tags else None,
                "source_provider": PROVIDER,
                "source_path": f"events_{competition}.json",
                "raw_tags": sorted(tags),
            }
        )
    player_rows = []
    for provider_player_id in used_player_ids:
        player = player_lookup.get(provider_player_id, {})
        birth_date = player.get("birthDate") or None
        age = None
        if birth_date:
            born = date.fromisoformat(birth_date)
            age = round((date(2018, 6, 30) - born).days / 365.2425, 1)
        role = player.get("role", {}) or {}
        player_rows.append(
            {
                "player_id": canonical_id("player", PROVIDER, provider_player_id),
                "provider_player_id": str(provider_player_id),
                "player_name": _full_name(player),
                "short_name": player.get("shortName"),
                "birth_date": birth_date,
                "age_at_season_end": age,
                "nationality": (player.get("passportArea") or {}).get("name"),
                "preferred_foot": player.get("foot"),
                "height_cm": player.get("height") or None,
                "weight_kg": player.get("weight") or None,
                "position": role.get("name"),
                "position_code": role.get("code3"),
                "source_provider": PROVIDER,
            }
        )
    team_rows = [
        {
            "team_id": canonical_id("team", PROVIDER, team["wyId"]),
            "provider_team_id": str(team["wyId"]),
            "team_name": team["name"],
            "source_provider": PROVIDER,
        }
        for team in teams_raw
    ]
    frames = {
        "matches": pl.DataFrame(match_rows),
        "players": pl.DataFrame(player_rows),
        "teams": pl.DataFrame(team_rows),
        "appearances": pl.DataFrame(appearance_rows),
        "events": pl.DataFrame(event_rows),
    }
    for name, frame in frames.items():
        frame.write_parquet(output / f"{name}.parquet", compression="zstd")
    return {name: frame.height for name, frame in frames.items()}
