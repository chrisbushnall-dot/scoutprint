from __future__ import annotations

from pathlib import Path

import polars as pl

from identity.build import season_start_year
from ingestion.wikidata_enrichment import normalize_name, normalize_team


def _competition_key(value: str | None) -> str:
    key = normalize_name(value)
    return {"epl": "premier league", "1 bundesliga": "bundesliga"}.get(key, key)


def _evidence_frame(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.col("player_name").map_elements(normalize_name, return_dtype=pl.String).alias("name_key"),
        pl.col("team_name").map_elements(normalize_team, return_dtype=pl.String).alias("team_key"),
        pl.col("competition_name")
        .map_elements(_competition_key, return_dtype=pl.String)
        .alias("competition_key_match"),
        pl.col("season_name")
        .map_elements(season_start_year, return_dtype=pl.Int64)
        .alias("season_year"),
    )


def classify_bigballs(bigballs: pl.DataFrame, candidates: pl.DataFrame) -> pl.DataFrame:
    """Classify source-local rows without ever accepting name-only evidence."""
    source = _evidence_frame(bigballs)
    trusted = _evidence_frame(candidates).filter(pl.col("source_provider") != "bigballs")
    candidate_rows = trusted.select(
        "canonical_player_id",
        "source_provider",
        "name_key",
        "team_key",
        "competition_key_match",
        "season_year",
    ).unique()
    exact_index: dict[tuple[str, str, str, int], set[str]] = {}
    competition_index: dict[tuple[str, str, int], set[str]] = {}
    name_season_index: dict[tuple[str, int], set[str]] = {}
    for row in candidate_rows.iter_rows(named=True):
        canonical = row["canonical_player_id"]
        if not canonical or not row["name_key"] or row["season_year"] is None:
            continue
        exact_index.setdefault(
            (
                row["name_key"],
                row["team_key"],
                row["competition_key_match"],
                row["season_year"],
            ),
            set(),
        ).add(canonical)
        competition_index.setdefault(
            (row["name_key"], row["competition_key_match"], row["season_year"]), set()
        ).add(canonical)
        name_season_index.setdefault((row["name_key"], row["season_year"]), set()).add(canonical)

    rows: list[dict] = []
    for row in source.iter_rows(named=True):
        exact = exact_index.get(
            (row["name_key"], row["team_key"], row["competition_key_match"], row["season_year"]),
            set(),
        )
        competition = competition_index.get(
            (row["name_key"], row["competition_key_match"], row["season_year"]), set()
        )
        name_season = name_season_index.get((row["name_key"], row["season_year"]), set())
        if len(exact) == 1:
            status, matches = "CONFIRMED", exact
            evidence = "exact normalized name+team+competition+season; unique canonical candidate"
        elif len(competition) == 1:
            status, matches = "PROBABLE", competition
            evidence = "exact normalized name+competition+season; team evidence absent or different"
        elif len(competition) > 1 or len(name_season) > 1:
            status, matches = "AMBIGUOUS", competition or name_season
            evidence = "multiple canonical candidates at name/competition/season evidence level"
        else:
            status, matches = "UNRESOLVED", name_season
            evidence = "no corroborated team+competition+season candidate"
        rows.append(
            {
                "source_provider": "bigballs",
                "player_id": row["player_id"],
                "player_name": row["player_name"],
                "team_name": row["team_name"],
                "competition_name": row["competition_name"],
                "season_name": row["season_name"],
                "identity_status": status,
                "matched_canonical_player_id": next(iter(matches)) if len(matches) == 1 else None,
                "candidate_count": len(matches),
                "evidence": evidence,
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None)


def run_bigballs_identity_audit(data_dir: Path) -> dict[str, int]:
    provider = pl.read_parquet(data_dir / "private/recent/providers/bigballs.parquet")
    history_path = data_dir / "private/canonical_identity/player_season_history.parquet"
    history = pl.read_parquet(history_path)
    review = classify_bigballs(provider, history)
    state = data_dir / "private/state"
    state.mkdir(parents=True, exist_ok=True)
    review.write_parquet(state / "bigballs_identity_review.parquet", compression="zstd")

    confirmed = review.filter(pl.col("identity_status") == "CONFIRMED").select(
        "source_provider", "player_id", "matched_canonical_player_id", "evidence"
    )
    links_path = data_dir / "private/canonical_identity/player_identity_links.parquet"
    links = pl.read_parquet(links_path)
    if confirmed.height:
        links = links.join(confirmed, on=["source_provider", "player_id"], how="left").with_columns(
            pl.col("matched_canonical_player_id")
            .fill_null(pl.col("canonical_player_id"))
            .alias("canonical_player_id"),
            pl.when(pl.col("matched_canonical_player_id").is_not_null())
            .then(pl.lit("exact_name+team+competition+season"))
            .otherwise(pl.col("matching_method"))
            .alias("matching_method"),
            pl.when(pl.col("matched_canonical_player_id").is_not_null())
            .then(pl.lit(0.99))
            .otherwise(pl.col("confidence"))
            .alias("confidence"),
            pl.when(pl.col("matched_canonical_player_id").is_not_null())
            .then(pl.col("evidence_right"))
            .otherwise(pl.col("evidence"))
            .alias("evidence"),
            pl.when(pl.col("matched_canonical_player_id").is_not_null())
            .then(pl.lit("matched_cross_provider"))
            .otherwise(pl.col("match_status"))
            .alias("match_status"),
        ).drop("matched_canonical_player_id", "evidence_right")
        links.write_parquet(links_path, compression="zstd")

    counts = review.group_by("identity_status").len()
    result = {row["identity_status"].lower(): row["len"] for row in counts.iter_rows(named=True)}
    result["total"] = review.height
    return result


def build_completeness_audit(data_dir: Path) -> pl.DataFrame:
    bigballs = pl.read_parquet(data_dir / "private/recent/providers/bigballs.parquet")
    denominators: dict[tuple[str, str], tuple[int, str]] = {}
    history = pl.read_parquet(data_dir / "private/canonical_identity/player_season_history.parquet")
    full = history.filter(
        (pl.col("source_provider") == "impect")
        & (pl.col("competition_name") == "Bundesliga")
        & (pl.col("season_name") == "2023/24")
    )
    if full.height:
        denominators[("Bundesliga", "2023")] = (full["player_id"].n_unique(), "Impect full league")
    rows: list[dict] = []
    for row in (
        bigballs.group_by("competition_name", "season_name")
        .agg(pl.len().alias("retrieved_players"))
        .sort("season_name", "competition_name")
        .iter_rows(named=True)
    ):
        denominator = denominators.get((row["competition_name"], row["season_name"]))
        rows.append(
            {
                **row,
                "known_population": denominator[0] if denominator else None,
                "denominator_source": denominator[1] if denominator else None,
                "coverage_ratio": row["retrieved_players"] / denominator[0] if denominator else None,
                "coverage_status": "measured_partial" if denominator else "denominator_pending",
            }
        )
    output = pl.DataFrame(rows, infer_schema_length=None)
    output.write_parquet(
        data_dir / "private/state/bigballs_completeness.parquet", compression="zstd"
    )
    return output
