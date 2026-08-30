from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from providers.cached_api import CachedJsonClient

BASE_URL = "https://api.sportmonks.com/v3/football"
TERMS_URL = "https://www.sportmonks.com/terms-and-conditions/"
FREE_LEAGUE_IDS = {271: "Danish Superliga", 501: "Scottish Premiership"}
TARGET_NAMES = {"2023/2024", "2024/2025", "2025/2026"}


class SportmonksProvider:
    name = "sportmonks"

    def __init__(self, data_dir: Path, api_token: str | None = None) -> None:
        self.api_token = api_token or os.getenv("SPORTMONKS_API_TOKEN")
        self.client = CachedJsonClient(
            self.name,
            data_dir / "private" / "raw" / self.name,
            usage_class="PRIVATE_GREEN",
            terms_url=TERMS_URL,
            delay_seconds=0.35,
        )

    def _params(self, **values: Any) -> dict[str, Any]:
        if not self.api_token:
            raise RuntimeError("SPORTMONKS_API_TOKEN is required")
        return {"api_token": self.api_token, **values}

    def fetch_coverage(self) -> dict[str, Any]:
        leagues = self.client.get(
            "coverage/leagues.json", f"{BASE_URL}/leagues", params=self._params(per_page=50)
        )
        page = 1
        season_rows: list[dict[str, Any]] = []
        while True:
            seasons = self.client.get(
                f"coverage/seasons/page={page}.json",
                f"{BASE_URL}/seasons",
                params=self._params(per_page=50, page=page),
            )
            if isinstance(seasons, dict):
                season_rows.extend(seasons.get("data", []))
                if seasons.get("pagination", {}).get("has_more"):
                    page += 1
                    continue
            break
        return {"leagues": leagues, "seasons": {"data": season_rows}}

    def fetch_season_players(self, season_id: int) -> list[Path]:
        """Fetch exact season participants, then each historical squad once."""
        page = 1
        paths: list[Path] = []
        while True:
            relative = f"teams/season={season_id}/page={page}.json"
            payload = self.client.get(
                relative,
                f"{BASE_URL}/teams/seasons/{season_id}",
                params=self._params(per_page=50, page=page),
            )
            paths.append(self.client.raw_dir / relative)
            for team in payload.get("data", []) if isinstance(payload, dict) else []:
                team_id = int(team["id"])
                squad_relative = f"squads/season={season_id}/team={team_id}.json"
                self.client.get(
                    squad_relative,
                    f"{BASE_URL}/squads/seasons/{season_id}/teams/{team_id}",
                    params=self._params(include="player.nationality;player.position;details.type"),
                )
                paths.append(self.client.raw_dir / squad_relative)
            pagination = payload.get("pagination", {}) if isinstance(payload, dict) else {}
            if not pagination.get("has_more"):
                return paths
            page += 1
