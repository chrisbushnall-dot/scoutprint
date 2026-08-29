from __future__ import annotations

import json
import math
import re
from pathlib import Path

import duckdb
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "football_scout.duckdb"
OUTPUT_DIR = ROOT / "web" / "data"
CHUNK_SIZE = 50

FINGERPRINTS = {
    "all": "fp_all_actions",
    "shots": "fp_shots",
    "goals": "fp_goals",
    "chances": "fp_chance_creation",
    "passes": "fp_passes",
    "defence": "fp_defensive_actions",
}
METRICS = [
    "goals_p90",
    "assists_p90",
    "shots_p90",
    "chance_creation_p90",
    "passes_p90",
    "defensive_actions_p90",
    "pct_attacking_third",
    "pct_penalty_area",
    "pct_half_space",
    "pct_central",
    "pct_wide",
    "box_presence_rate",
]


def decode_escaped_unicode(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match.group(1), 16)), value)


def finite(value: object) -> float | int | str | bool | None:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def quantize(vector: object) -> list[int]:
    return [round(float(value) * 10000) for value in vector]


def main() -> None:
    with duckdb.connect(str(DATABASE), read_only=True) as connection:
        frame = connection.execute("SELECT * EXCLUDE(filename) FROM player_seasons").fetchdf()
    scales = {}
    for metric in METRICS:
        values = frame[metric].dropna().to_numpy(dtype=float)
        low, high = np.percentile(values, [10, 90]) if len(values) else (0.0, 1.0)
        scales[metric] = {"low": round(float(low), 6), "high": round(float(high), 6)}

    players = []
    scalar_columns = [
        "player_season_id",
        "player_name",
        "team_name",
        "positions",
        "age",
        "nationality",
        "preferred_foot",
        "height_cm",
        "minutes",
        "appearances",
        "starts",
        "goals",
        "assists",
        *METRICS,
    ]
    for record in frame.to_dict(orient="records"):
        player = {column: finite(record.get(column)) for column in scalar_columns}
        for column in ("player_name", "team_name", "nationality"):
            player[column] = decode_escaped_unicode(player[column])
        player["fp"] = {name: quantize(record[column]) for name, column in FINGERPRINTS.items()}
        players.append(player)

    meta = {
            "competition": "Premier League",
            "season": "2017/18",
            "provider": "Wyscout public research dataset",
            "licence": "CC BY 4.0",
            "matches": 380,
            "located_events": 595119,
            "grid": [16, 12],
            "quantization": 10000,
            "scales": scales,
    }
    players = sorted(players, key=lambda player: player["player_name"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    chunks = []
    for index, offset in enumerate(range(0, len(players), CHUNK_SIZE)):
        name = f"profiles-{index:02d}.json"
        path = OUTPUT_DIR / name
        path.write_text(
            json.dumps(players[offset : offset + CHUNK_SIZE], ensure_ascii=False, separators=(",", ":"))
            + "\n"
        )
        chunks.append(name)
    index_path = OUTPUT_DIR / "index.json"
    index_path.write_text(
        json.dumps({"meta": meta, "chunks": chunks}, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    total_bytes = sum((OUTPUT_DIR / name).stat().st_size for name in ["index.json", *chunks])
    print(f"Exported {len(players)} profiles in {len(chunks)} chunks ({total_bytes:,} bytes)")


if __name__ == "__main__":
    main()
