from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from similarity.intelligence import (
    ROLE_TAXONOMY,
    SCORE_METHOD_VERSION,
    build_player_intelligence,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Scoutprint's derived product intelligence from canonical history"
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def _signature(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def rebuild(data_dir: Path, force: bool = False) -> dict[str, object]:
    source = data_dir / "private" / "canonical_identity" / "player_season_history.parquet"
    output_dir = data_dir / "private" / "product"
    output = output_dir / "player_intelligence.parquet"
    manifest = output_dir / "manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    signature = _signature(source)
    if manifest.exists() and output.exists() and not force:
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        if previous.get("source_signature") == signature:
            return {**previous, "state": "unchanged"}

    history = pl.read_parquet(source).to_pandas()
    intelligence = build_player_intelligence(history)
    with tempfile.NamedTemporaryFile(
        dir=output_dir, prefix="player-intelligence-", suffix=".parquet", delete=False
    ) as handle:
        temporary = Path(handle.name)
    try:
        pl.from_pandas(intelligence).write_parquet(temporary, compression="zstd")
        # Read the staged file before atomic replacement so failed builds preserve last-known-good.
        staged = pl.scan_parquet(temporary).select(pl.len()).collect().item()
        if staged != len(intelligence) or staged < 1:
            raise RuntimeError("Staged intelligence validation failed")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    role_counts = intelligence["primary_role"].value_counts().to_dict()
    report: dict[str, object] = {
        "state": "rebuilt",
        "built_at": datetime.now(UTC).isoformat(),
        "score_method_version": SCORE_METHOD_VERSION,
        "source_signature": signature,
        "player_seasons": len(intelligence),
        "players": int(intelligence["canonical_person_id"].nunique()),
        "development_available": int(intelligence["development"].notna().sum()),
        "spatial_change_available": int(intelligence["spatial_change"].notna().sum()),
        "taxonomy_roles": len(ROLE_TAXONOMY),
        "role_counts": role_counts,
    }
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    args = parse_args()
    print(json.dumps(rebuild(args.data_dir, args.force), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
