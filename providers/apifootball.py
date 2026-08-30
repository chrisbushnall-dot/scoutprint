from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from providers.cached_api import CachedJsonClient

BASE_URL = "https://apiv3.apifootball.com/"
TERMS_URL = "https://apifootball.com/terms_of_use/"
TARGET_SEASONS = {"2023/2024", "2024/2025", "2025/2026"}
TARGET_LEAGUES = {"Championship", "Ligue 2"}


class ApiFootballComProvider:
    name = "apifootball_com"

    def __init__(self, data_dir: Path, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("APIFOOTBALL_API_KEY")
        self.client = CachedJsonClient(
            self.name,
            data_dir / "private" / "raw" / self.name,
            usage_class="PRIVATE_GREEN",
            terms_url=TERMS_URL,
            delay_seconds=0.35,
        )

    def _params(self, **values: Any) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("APIFOOTBALL_API_KEY is required")
        return {"APIkey": self.api_key, **values}

    def fetch_coverage(self) -> list[dict[str, Any]]:
        payload = self.client.get(
            "coverage/leagues.json", BASE_URL, params=self._params(action="get_leagues")
        )
        if not isinstance(payload, list):
            raise TypeError("Unexpected APIFootball.com coverage response")
        return payload

    def fetch_target_leagues(self) -> list[Path]:
        paths: list[Path] = []
        for league in self.fetch_coverage():
            if league.get("league_name") not in TARGET_LEAGUES:
                continue
            if league.get("league_season") not in TARGET_SEASONS:
                continue
            league_id = str(league["league_id"])
            relative = f"teams/league={league_id}.json"
            self.client.get(
                relative,
                BASE_URL,
                params=self._params(action="get_teams", league_id=league_id),
            )
            paths.append(self.client.raw_dir / relative)
        return paths
