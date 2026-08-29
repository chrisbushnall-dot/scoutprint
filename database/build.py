from __future__ import annotations

from pathlib import Path

import duckdb


def build_database(data_dir: Path, database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database_path)) as connection:
        normalized = str(data_dir / "normalized" / "*" / "competition=*" / "season=*" / "*.parquet")
        derived = str(data_dir / "derived" / "player_seasons_*.parquet")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS ingestion_runs(run_at TIMESTAMP DEFAULT current_timestamp, provider VARCHAR, status VARCHAR, details JSON)"
        )
        for name in ("matches", "players", "appearances", "events"):
            path = normalized.replace("*.parquet", f"{name}.parquet")
            sql_path = path.replace("'", "''")
            connection.execute(
                f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{sql_path}', union_by_name=true, filename=true)"
            )
        sql_derived = derived.replace("'", "''")
        connection.execute(
            f"CREATE OR REPLACE VIEW player_seasons AS SELECT * FROM read_parquet('{sql_derived}', union_by_name=true, filename=true)"
        )
