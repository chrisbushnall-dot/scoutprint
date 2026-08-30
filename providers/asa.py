from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from itscalledsoccer.client import AmericanSoccerAnalysis

from providers.cached_api import sha256_bytes, write_provenance

TERMS_URL = "https://github.com/American-Soccer-Analysis/itscalledsoccer"
TARGET_LEAGUES = {
    "mls": "Major League Soccer",
    "uslc": "USL Championship",
    "usl1": "USL League One",
    "mlsnp": "MLS NEXT Pro",
}
TARGET_SEASONS = (2024, 2025, 2026)


class AmericanSoccerAnalysisProvider:
    """Cached client for ASA's official, public, unauthenticated API wrapper."""

    name = "american_soccer_analysis"

    def __init__(self, data_dir: Path) -> None:
        self.raw_dir = data_dir / "private" / "raw" / self.name
        self.client = AmericanSoccerAnalysis()

    def _cache_frame(self, relative: str, frame_factory) -> Path:
        destination = self.raw_dir / relative
        if destination.exists() and destination.stat().st_size:
            return destination
        frame = self._parquet_safe(frame_factory())
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        frame.to_parquet(temporary, index=False)
        temporary.replace(destination)
        content = destination.read_bytes()
        write_provenance(
            destination,
            {
                "provider": self.name,
                "source_url": "https://app.americansocceranalysis.com/api/v1/",
                "official_client": TERMS_URL,
                "usage_class": "PRIVATE_GREEN",
                "storage": "private_vps_only",
                "retrieved_at": datetime.now(UTC).isoformat(),
                "checksum_sha256": sha256_bytes(content),
                "bytes": len(content),
                "rows": len(frame),
            },
        )
        return destination

    @staticmethod
    def _parquet_safe(frame: pd.DataFrame) -> pd.DataFrame:
        """Serialize heterogeneous object values without altering uniform list columns."""
        frame = frame.copy()
        for column in frame.select_dtypes(include="object").columns:
            values = frame[column].dropna()
            types = {type(value) for value in values}
            if dict in types or (list in types and len(types) > 1):
                frame[column] = frame[column].map(
                    lambda value: (
                        json.dumps(value, sort_keys=True)
                        if isinstance(value, (dict, list))
                        else value
                    )
                )
        return frame

    def fetch_coverage(self) -> pd.DataFrame:
        rows: list[dict[str, int | str]] = []
        for league, competition in TARGET_LEAGUES.items():
            path = self._cache_frame(
                f"coverage/{league}_games.parquet",
                lambda league=league: self.client.get_games(leagues=league),
            )
            games = pd.read_parquet(path)
            counts = games.groupby("season_name", dropna=True).size()
            for season, matches in counts.items():
                if int(season) in TARGET_SEASONS:
                    rows.append(
                        {
                            "league": league,
                            "competition": competition,
                            "season": int(season),
                            "matches": int(matches),
                        }
                    )
        return pd.DataFrame(rows).sort_values(["league", "season"]).reset_index(drop=True)

    def fetch_recent(self) -> list[Path]:
        paths: list[Path] = []
        for league in TARGET_LEAGUES:
            paths.append(
                self._cache_frame(
                    f"entities/{league}_players.parquet",
                    lambda league=league: self.client.get_players(leagues=league),
                )
            )
            paths.append(
                self._cache_frame(
                    f"entities/{league}_teams.parquet",
                    lambda league=league: self.client.get_teams(leagues=league),
                )
            )
            for season in TARGET_SEASONS:
                common = {
                    "leagues": league,
                    "season_name": str(season),
                    "split_by_seasons": True,
                    "split_by_teams": True,
                }
                endpoints = {
                    "xgoals": self.client.get_player_xgoals,
                    "xpass": self.client.get_player_xpass,
                    "goals_added": self.client.get_player_goals_added,
                }
                for name, method in endpoints.items():
                    paths.append(
                        self._cache_frame(
                            f"stats/{league}/{season}_{name}.parquet",
                            lambda method=method, common=common: method(**common),
                        )
                    )
        manifest = self.raw_dir / "manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps({"leagues": TARGET_LEAGUES, "seasons": TARGET_SEASONS}, indent=2) + "\n"
        )
        return paths
