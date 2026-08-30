from __future__ import annotations

import os
from pathlib import Path

from ingestion.api_football_smoke import run_league_season_smoke


def main() -> None:
    data_dir = Path(os.getenv("FOOTBALL_SCOUT_DATA_DIR", "data"))
    print(run_league_season_smoke(data_dir))


if __name__ == "__main__":
    main()
