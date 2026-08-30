from __future__ import annotations

import os
from pathlib import Path

from ingestion.recent import build_recent_player_seasons, normalize_asa
from providers.asa import AmericanSoccerAnalysisProvider


def main() -> None:
    data_dir = Path(os.getenv("FOOTBALL_SCOUT_DATA_DIR", "data"))
    provider = AmericanSoccerAnalysisProvider(data_dir)
    coverage = provider.fetch_coverage()
    provider.fetch_recent()
    normalized = normalize_asa(data_dir)
    canonical = build_recent_player_seasons(data_dir)
    print(coverage.to_string(index=False))
    print({"normalized": normalized, "canonical": canonical})


if __name__ == "__main__":
    main()
