from __future__ import annotations

import os
from pathlib import Path

from ingestion.keyed_recent import (
    normalize_apifootball_com,
    normalize_bigballs,
    normalize_sportmonks,
)
from providers.apifootball import ApiFootballComProvider
from providers.bigballs import BigBallsProvider
from providers.sportmonks import FREE_LEAGUE_IDS, SportmonksProvider


def main() -> None:
    data_dir = Path(os.getenv("FOOTBALL_SCOUT_DATA_DIR", "data"))
    completed: list[str] = []
    if os.getenv("BIGBALLS_API_KEY"):
        BigBallsProvider(data_dir).fetch_top_five()
        normalize_bigballs(data_dir)
        completed.append("bigballs")
    if os.getenv("SPORTMONKS_API_TOKEN"):
        provider = SportmonksProvider(data_dir)
        coverage = provider.fetch_coverage()
        for season in coverage["seasons"].get("data", []):
            if season.get("league_id") in FREE_LEAGUE_IDS and season.get("name") in {
                "2023/2024",
                "2024/2025",
                "2025/2026",
            }:
                provider.fetch_season_players(int(season["id"]))
        normalize_sportmonks(data_dir)
        completed.append("sportmonks")
    if os.getenv("APIFOOTBALL_API_KEY"):
        ApiFootballComProvider(data_dir).fetch_target_leagues()
        normalize_apifootball_com(data_dir)
        completed.append("apifootball_com")
    print({"completed": completed})


if __name__ == "__main__":
    main()
