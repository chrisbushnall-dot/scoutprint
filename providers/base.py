from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SourceProvenance:
    provider: str
    source_url: str
    licence_name: str
    licence_url: str
    retrieved_at: str
    checksum_sha256: str


class EventProvider(Protocol):
    name: str

    def fetch_competition(self, competition_id: int, season_id: int, limit: int = 0) -> list[Path]:
        """Fetch a competition season idempotently and return cached paths."""

    def normalize(self, competition_id: int, season_id: int) -> None:
        """Normalize cached provider data into the canonical model."""
