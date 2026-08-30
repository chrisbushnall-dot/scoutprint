from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from providers.cached_api import CachedJsonClient

BASE_URL = "https://api.bigballsdata.com"
TERMS_URL = "https://bigballsdata.com/legal/terms"
LEAGUES = {
    "epl": "Premier League",
    "laliga": "La Liga",
    "bundesliga": "Bundesliga",
    "serie-a": "Serie A",
    "ligue-1": "Ligue 1",
}
TARGET_SEASONS = (2023, 2024, 2025)
SORT_METRICS = ("xg", "xa", "npxg", "goals", "assists", "shots", "key_passes")


class BigBallsProvider:
    name = "bigballs"

    def __init__(self, data_dir: Path, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("BIGBALLS_API_KEY")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else None
        self.client = CachedJsonClient(
            self.name,
            data_dir / "private" / "raw" / self.name,
            usage_class="PRIVATE_GREEN",
            terms_url=TERMS_URL,
            delay_seconds=0.65,
            headers=headers,
        )

    def fetch_coverage(self, *, force: bool = False) -> dict[str, Any]:
        payload = self.client.get(
            "coverage/football.json",
            f"{BASE_URL}/v1/coverage",
            params={"sport": "football"},
            force=force,
        )
        if not isinstance(payload, dict):
            raise TypeError("Unexpected Big Balls coverage response")
        return payload

    def fetch_top_five(self, seasons: tuple[int, ...] = TARGET_SEASONS) -> list[Path]:
        if not self.api_key:
            raise RuntimeError("BIGBALLS_API_KEY is required for player-stat endpoints")
        paths: list[Path] = []
        for league in LEAGUES:
            for season in seasons:
                for metric in SORT_METRICS:
                    relative = f"xg_leaders/{league}/{season}/{metric}.json"
                    self.client.get(
                        relative,
                        f"{BASE_URL}/v1/leagues/{league}/xg-leaders",
                        params={"season": season, "stat": metric, "min_minutes": 0, "limit": 100},
                    )
                    paths.append(self.client.raw_dir / relative)
        return paths
