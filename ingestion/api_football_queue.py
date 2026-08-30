from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from ingestion.api_football_normalize import build_provider_table, normalize_player_page
from ingestion.api_football_priority import build_priority_matrix
from providers.api_football import ApiFootballEntitlementError, ApiFootballProvider

QUEUE_COLUMNS = {
    "league": pl.Int64,
    "competition": pl.String,
    "country": pl.String,
    "season": pl.Int64,
    "team": pl.Int64,
    "item_type": pl.String,
    "page": pl.Int64,
    "priority": pl.Int64,
    "status": pl.String,
    "attempts": pl.Int64,
    "last_attempt": pl.String,
    "checksum": pl.String,
}

PRIORITY_NAMES = (
    "Premier League",
    "La Liga",
    "Bundesliga",
    "Serie A",
    "Ligue 1",
    "Eredivisie",
    "Primeira Liga",
    "Championship",
    "Major League Soccer",
)


def _queue_path(data_dir: Path) -> Path:
    return data_dir / "private" / "state" / "api_football_queue.parquet"


def _priority(competition: str, country: str) -> int:
    if competition in PRIORITY_NAMES:
        return PRIORITY_NAMES.index(competition)
    preferred_countries = (
        "Belgium",
        "Austria",
        "Switzerland",
        "Denmark",
        "Norway",
        "Sweden",
        "Poland",
        "Czech-Republic",
        "Croatia",
        "Serbia",
        "Brazil",
        "Argentina",
        "Japan",
        "South-Korea",
    )
    return 20 + preferred_countries.index(country) if country in preferred_countries else 100


def initialize_queue(data_dir: Path, coverage: pl.DataFrame) -> pl.DataFrame:
    path = _queue_path(data_dir)
    prior = pl.read_parquet(path) if path.exists() else pl.DataFrame(schema=QUEUE_COLUMNS)
    if "selected" in coverage.columns:
        coverage = coverage.filter(pl.col("selected"))
        selected_keys = coverage.select(
            pl.col("league_id").alias("league"), "season"
        ).unique()
        if prior.height:
            prior = prior.join(selected_keys, on=["league", "season"], how="semi")
    rows = [
        {
            "league": int(row["league_id"]),
            "competition": row["competition"],
            "country": row["country"],
            "season": int(row["season"]),
            "team": None,
            "item_type": "teams",
            "page": 0,
            "priority": int(row.get("priority") or _priority(row["competition"], row["country"])),
            "status": "pending",
            "attempts": 0,
            "last_attempt": None,
            "checksum": None,
        }
        for row in coverage.iter_rows(named=True)
    ]
    new = pl.DataFrame(rows, schema=QUEUE_COLUMNS)
    combined = pl.concat([prior, new], how="diagonal_relaxed").unique(
        ["league", "season", "team", "item_type", "page"], keep="first"
    )
    return _write_queue(path, combined)


def _write_queue(path: Path, queue: pl.DataFrame) -> pl.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    queue = queue.sort("priority", "season", "league", "page", descending=[False, True, False, False])
    temporary = path.with_suffix(".parquet.part")
    queue.write_parquet(temporary, compression="zstd")
    temporary.replace(path)
    return queue


def _checksum_for_path(path: Path) -> str:
    metadata = path.with_suffix(path.suffix + ".meta.json")
    return json.loads(metadata.read_text())["checksum_sha256"]


def network_requests_today(data_dir: Path, *, now: datetime | None = None) -> int:
    today = (now or datetime.now(UTC)).date()
    count = 0
    for path in (data_dir / "private/raw/api_football").glob("**/*.meta.json"):
        try:
            retrieved = datetime.fromisoformat(json.loads(path.read_text())["retrieved_at"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        if retrieved.astimezone(UTC).date() == today:
            count += 1
    return count


def run_daily_batch(data_dir: Path, *, request_budget: int = 92) -> dict[str, int]:
    """Download at most request_budget uncached pages and persist progress after every page."""
    if not 1 <= request_budget <= 95:
        raise ValueError("request_budget must be between 1 and 95")
    provider = ApiFootballProvider(data_dir)
    queue_path = _queue_path(data_dir)
    if not queue_path.exists():
        coverage = provider.fetch_coverage()
        matrix = build_priority_matrix(data_dir, coverage)
        queue = initialize_queue(data_dir, matrix)
        network_calls = 0
    else:
        queue = pl.read_parquet(queue_path)
        network_calls = 0
    completed = 0
    failed = 0
    used_before = network_requests_today(data_dir)
    allowance = max(0, min(request_budget, 92) - used_before)
    while network_calls < allowance:
        pending = queue.filter(pl.col("status").is_in(["pending", "retry"])).sort(
            "priority", "season", "league", "page"
        )
        if not pending.height:
            break
        item = pending.row(0, named=True)
        league, season, page = item["league"], item["season"], item["page"]
        team, item_type = item["team"], item["item_type"]
        raw_path = (
            provider.client.raw_dir / f"teams/league={league}/season={season}.json"
            if item_type == "teams"
            else provider.client.raw_dir
            / f"players/league={league}/season={season}/team={team}/page={page}.json"
        )
        was_cached = raw_path.exists() and raw_path.stat().st_size > 0
        now = datetime.now(UTC).isoformat()
        selector = (
            (pl.col("league") == league) & (pl.col("season") == season) & (pl.col("page") == page)
            & (pl.col("item_type") == item_type)
            & (pl.col("team").fill_null(-1) == (team if team is not None else -1))
        )
        try:
            payload = (
                provider.fetch_teams(league, season)
                if item_type == "teams"
                else provider.fetch_team_player_page(league, season, int(team), page)
            )
            if not was_cached:
                network_calls += 1
            paging = payload.get("paging", {})
            if item_type == "players":
                total_pages = max(int(paging.get("total") or page), page)
                if total_pages > 3:
                    season_selector = (pl.col("league") == league) & (
                        pl.col("season") == season
                    )
                    queue = queue.with_columns(
                        pl.when(season_selector)
                        .then(pl.lit("blocked_page_ceiling"))
                        .otherwise(pl.col("status"))
                        .alias("status"),
                        pl.when(selector)
                        .then(pl.col("attempts") + 1)
                        .otherwise(pl.col("attempts"))
                        .alias("attempts"),
                        pl.when(selector)
                        .then(pl.lit(now))
                        .otherwise(pl.col("last_attempt"))
                        .alias("last_attempt"),
                    )
                    failed += 1
                    queue = _write_queue(queue_path, queue)
                    continue
                normalize_player_page(
                    data_dir,
                    payload,
                    league_id=league,
                    season=season,
                    page=int(team) * 10 + page,
                )
            else:
                total_pages = 1
            queue = queue.with_columns(
                pl.when(selector)
                .then(pl.lit("complete"))
                .otherwise(pl.col("status"))
                .alias("status"),
                pl.when(selector)
                .then(pl.col("attempts") + 1)
                .otherwise(pl.col("attempts"))
                .alias("attempts"),
                pl.when(selector)
                .then(pl.lit(now))
                .otherwise(pl.col("last_attempt"))
                .alias("last_attempt"),
                pl.when(selector)
                .then(pl.lit(_checksum_for_path(raw_path)))
                .otherwise(pl.col("checksum"))
                .alias("checksum"),
            )
            existing = {
                (row["team"], row["item_type"], row["page"])
                for row in queue.filter(
                    (pl.col("league") == league) & (pl.col("season") == season)
                ).iter_rows(named=True)
            }
            if item_type == "teams":
                additions = [
                    {
                        **item,
                        "team": int(entry["team"]["id"]),
                        "item_type": "players",
                        "page": 1,
                        "status": "pending",
                        "attempts": 0,
                        "last_attempt": None,
                        "checksum": None,
                    }
                    for entry in payload.get("response") or []
                    if (int(entry["team"]["id"]), "players", 1) not in existing
                ]
            else:
                additions = [
                    {
                        **item,
                        "page": next_page,
                        "status": "pending",
                        "attempts": 0,
                        "last_attempt": None,
                        "checksum": None,
                    }
                    for next_page in range(page + 1, total_pages + 1)
                    if (team, "players", next_page) not in existing
                ]
            if additions:
                queue = pl.concat(
                    [queue, pl.DataFrame(additions, schema=QUEUE_COLUMNS)], how="diagonal_relaxed"
                )
            completed += 1
        except ApiFootballEntitlementError:
            queue = queue.with_columns(
                pl.when(selector).then(pl.lit("blocked_entitlement")).otherwise(pl.col("status")).alias("status"),
                pl.when(selector)
                .then(pl.col("attempts") + 1)
                .otherwise(pl.col("attempts"))
                .alias("attempts"),
                pl.when(selector)
                .then(pl.lit(now))
                .otherwise(pl.col("last_attempt"))
                .alias("last_attempt"),
            )
            failed += 1
            queue = _write_queue(queue_path, queue)
            continue
        except Exception:
            queue = queue.with_columns(
                pl.when(selector).then(pl.lit("retry")).otherwise(pl.col("status")).alias("status"),
                pl.when(selector)
                .then(pl.col("attempts") + 1)
                .otherwise(pl.col("attempts"))
                .alias("attempts"),
                pl.when(selector)
                .then(pl.lit(now))
                .otherwise(pl.col("last_attempt"))
                .alias("last_attempt"),
            )
            failed += 1
            _write_queue(queue_path, queue)
            raise
        queue = _write_queue(queue_path, queue)
    build_provider_table(data_dir)
    return {
        "network_calls": network_calls,
        "daily_requests_before": used_before,
        "daily_request_cap": 92,
        "completed_pages": completed,
        "failed_pages": failed,
        "remaining_pages": queue.filter(pl.col("status").is_in(["pending", "retry"])).height,
    }
