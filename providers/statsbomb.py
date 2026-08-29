from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"


class StatsBombOpenDataProvider:
    """Polite cached downloader for StatsBomb's official Open Data repository."""

    name = "statsbomb_open_data"

    def __init__(self, data_dir: Path, delay_seconds: float = 0.05) -> None:
        self.raw_dir = data_dir / "raw" / self.name
        self.state_dir = data_dir / "state"
        self.delay_seconds = delay_seconds
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "football-scout/0.1 (self-hosted research)"

    @staticmethod
    def _sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _fetch(self, relative: str) -> Path:
        destination = self.raw_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.stat().st_size:
            return destination
        response = self.session.get(f"{BASE_URL}/{relative}", timeout=60)
        response.raise_for_status()
        content = response.content
        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.write_bytes(content)
        temporary.replace(destination)
        metadata = {
            "provider": self.name,
            "source_url": f"{BASE_URL}/{relative}",
            "retrieved_at": datetime.now(UTC).isoformat(),
            "checksum_sha256": self._sha256(content),
            "bytes": len(content),
        }
        destination.with_suffix(destination.suffix + ".meta.json").write_text(
            json.dumps(metadata, indent=2) + "\n"
        )
        time.sleep(self.delay_seconds)
        return destination

    def fetch_competition(self, competition_id: int, season_id: int, limit: int = 0) -> list[Path]:
        paths = [self._fetch("competitions.json")]
        match_path = self._fetch(f"matches/{competition_id}/{season_id}.json")
        paths.append(match_path)
        matches = json.loads(match_path.read_text())
        if limit > 0:
            matches = matches[:limit]
        for index, match in enumerate(matches, start=1):
            match_id = int(match["match_id"])
            paths.append(self._fetch(f"events/{match_id}.json"))
            paths.append(self._fetch(f"lineups/{match_id}.json"))
            if index % 25 == 0:
                LOGGER.info("Downloaded/cached %s of %s matches", index, len(matches))
        return paths
