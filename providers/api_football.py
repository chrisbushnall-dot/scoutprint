from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import polars as pl

from providers.cached_api import CachedJsonClient

BASE_URL = "https://v3.football.api-sports.io"
TERMS_URL = "https://www.api-football.com/terms"
TARGET_SEASONS = (2023, 2024, 2025)


class ApiFootballEntitlementError(RuntimeError):
    pass


class ApiFootballRateLimitError(RuntimeError):
    pass


class ApiFootballProvider:
    name = "api_football"

    def __init__(self, data_dir: Path, api_key: str | None = None) -> None:
        self.data_dir = data_dir
        self.api_key = api_key or os.getenv("API_FOOTBALL_KEY")
        headers = {"x-apisports-key": self.api_key} if self.api_key else None
        self.client = CachedJsonClient(
            self.name,
            data_dir / "private" / "raw" / self.name,
            usage_class="PRIVATE_GREEN",
            terms_url=TERMS_URL,
            delay_seconds=6.2,
            headers=headers,
        )

    def _validate(self, payload: Any, relative: str, label: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError(f"Unexpected API-Football {label} response")
        if payload.get("errors"):
            quarantine = self.data_dir / "private/quarantine/api_football-errors" / relative
            quarantine.parent.mkdir(parents=True, exist_ok=True)
            raw = self.client.raw_dir / relative
            if raw.exists():
                shutil.move(raw, quarantine)
            metadata = raw.with_suffix(raw.suffix + ".meta.json")
            if metadata.exists():
                shutil.move(metadata, quarantine.with_suffix(quarantine.suffix + ".meta.json"))
            error = payload["errors"]
            if isinstance(error, dict) and "plan" in error:
                raise ApiFootballEntitlementError(
                    f"API-Football rejected {label} request: {error}"
                )
            if isinstance(error, dict) and "rateLimit" in error:
                raise ApiFootballRateLimitError(
                    f"API-Football rejected {label} request: {error}"
                )
            raise RuntimeError(f"API-Football rejected {label} request: {error}")
        return payload

    def _require_key(self) -> None:
        if not self.api_key:
            raise RuntimeError("API_FOOTBALL_KEY is required")

    def fetch_coverage(self) -> pl.DataFrame:
        self._require_key()
        payload = self.client.get("coverage/leagues.json", f"{BASE_URL}/leagues")
        rows: list[dict[str, Any]] = []
        for item in payload.get("response", []):
            league = item.get("league", {})
            country = item.get("country", {})
            for season in item.get("seasons", []):
                year = season.get("year")
                if year in TARGET_SEASONS:
                    rows.append(
                        {
                            "league_id": league.get("id"),
                            "competition": league.get("name"),
                            "country": country.get("name"),
                            "season": year,
                            "current": season.get("current"),
                            "coverage_json": json.dumps(season.get("coverage", {}), sort_keys=True),
                        }
                    )
        frame = pl.DataFrame(rows, infer_schema_length=None)
        output = self.data_dir / "private" / "state" / "api_football_coverage.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(output, compression="zstd")
        return frame

    def fetch_player_page(self, league: int, season: int, page: int) -> dict[str, Any]:
        self._require_key()
        relative = f"players/league={league}/season={season}/page={page}.json"
        payload = self.client.get(
            relative,
            f"{BASE_URL}/players",
            params={"league": league, "season": season, "page": page},
        )
        return self._validate(payload, relative, "player")

    def fetch_teams(self, league: int, season: int) -> dict[str, Any]:
        self._require_key()
        relative = f"teams/league={league}/season={season}.json"
        payload = self.client.get(
            relative,
            f"{BASE_URL}/teams",
            params={"league": league, "season": season},
        )
        return self._validate(payload, relative, "teams")

    def fetch_team_player_page(
        self, league: int, season: int, team: int, page: int
    ) -> dict[str, Any]:
        self._require_key()
        relative = f"players/league={league}/season={season}/team={team}/page={page}.json"
        payload = self.client.get(
            relative,
            f"{BASE_URL}/players",
            params={"league": league, "season": season, "team": team, "page": page},
        )
        return self._validate(payload, relative, "team-player")
