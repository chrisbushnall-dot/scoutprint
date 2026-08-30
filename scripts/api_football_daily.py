from __future__ import annotations

import argparse
import os
from pathlib import Path

from ingestion.api_football_queue import run_daily_batch


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the resumable API-Football daily collector")
    parser.add_argument("--request-budget", type=int, default=92)
    args = parser.parse_args()
    data_dir = Path(os.getenv("FOOTBALL_SCOUT_DATA_DIR", "data"))
    print(run_daily_batch(data_dir, request_budget=args.request_budget))


if __name__ == "__main__":
    main()
