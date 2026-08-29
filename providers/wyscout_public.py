from __future__ import annotations

import hashlib
import json
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import requests

FIGSHARE_FILES = {
    "players.json": "https://ndownloader.figshare.com/files/15073721",
    "teams.json": "https://ndownloader.figshare.com/files/15073697",
    "competitions.json": "https://ndownloader.figshare.com/files/15073685",
    "events.zip": "https://ndownloader.figshare.com/files/14464685",
    "matches.zip": "https://ndownloader.figshare.com/files/14464622",
    "eventid2name.csv": "https://ndownloader.figshare.com/files/21385245",
    "tags2name.csv": "https://ndownloader.figshare.com/files/21385239",
}


class WyscoutPublicProvider:
    """Cached adapter for Pappalardo et al.'s CC BY 4.0 Figshare release."""

    name = "wyscout_public"

    def __init__(self, data_dir: Path) -> None:
        self.raw_dir = data_dir / "raw" / self.name
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "football-scout/0.1 (CC-BY research dataset client)"

    def _fetch(self, name: str, url: str) -> Path:
        destination = self.raw_dir / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.stat().st_size:
            return destination
        response = self.session.get(url, timeout=180)
        response.raise_for_status()
        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.write_bytes(response.content)
        temporary.replace(destination)
        metadata = {
            "provider": self.name,
            "source_url": url,
            "figshare_collection": "https://doi.org/10.6084/m9.figshare.c.4415000.v5",
            "licence": "CC BY 4.0",
            "licence_url": "https://creativecommons.org/licenses/by/4.0/",
            "retrieved_at": datetime.now(UTC).isoformat(),
            "checksum_sha256": hashlib.sha256(response.content).hexdigest(),
            "bytes": len(response.content),
        }
        destination.with_suffix(destination.suffix + ".meta.json").write_text(
            json.dumps(metadata, indent=2) + "\n"
        )
        time.sleep(0.1)
        return destination

    def fetch_competition(self, competition: str = "England") -> list[Path]:
        paths = [self._fetch(name, url) for name, url in FIGSHARE_FILES.items()]
        for archive_name in ("events.zip", "matches.zip"):
            archive = self.raw_dir / archive_name
            expected = f"{archive_name.removesuffix('.zip')}_{competition}.json"
            output = self.raw_dir / expected
            if not output.exists():
                with zipfile.ZipFile(archive) as zipped:
                    member = next(name for name in zipped.namelist() if Path(name).name == expected)
                    with zipped.open(member) as source:
                        temporary = output.with_suffix(".json.part")
                        temporary.write_bytes(source.read())
                        temporary.replace(output)
            paths.append(output)
        return paths
