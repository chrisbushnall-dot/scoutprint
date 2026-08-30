from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import polars as pl

from ingestion.statsbomb import canonical_id
from ingestion.wikidata_enrichment import normalize_name, normalize_team


def normalize_nationality(value: str | None) -> str:
    return normalize_name(value)


def season_start_year(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(str(value).split("/")[0])
    except ValueError:
        return None


class UnionFind:
    def __init__(self, values: list[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def _player_records(data_dir: Path) -> pl.DataFrame:
    paths = sorted(
        [
            *data_dir.glob("normalized/*/competition=*/season=*/players.parquet"),
            *data_dir.glob("private/canonical/*/competition=*/season=*/players.parquet"),
            *data_dir.glob("private/recent/providers/*.parquet"),
        ]
    )
    frames = [pl.read_parquet(path) for path in paths]
    combined = pl.concat(frames, how="diagonal_relaxed")
    if "acquisition_complete" in combined.columns:
        combined = combined.filter(
            (pl.col("source_provider") != "api_football")
            | pl.col("acquisition_complete").fill_null(False)
        )
    desired = {
        "birth_date": pl.String,
        "nationality": pl.String,
        "provider_player_id": pl.String,
    }
    for column, dtype in desired.items():
        if column not in combined.columns:
            combined = combined.with_columns(pl.lit(None, dtype=dtype).alias(column))
    players = (
        combined.select(
            "source_provider",
            "player_id",
            "provider_player_id",
            "player_name",
            "birth_date",
            "nationality",
        )
        .group_by("source_provider", "player_id")
        .agg(
            pl.col("provider_player_id").drop_nulls().first(),
            pl.col("player_name").drop_nulls().first(),
            pl.col("birth_date").drop_nulls().first(),
            pl.col("nationality").drop_nulls().first(),
        )
        .with_columns(
            pl.col("player_name")
            .map_elements(normalize_name, return_dtype=pl.String)
            .alias("normalized_name"),
            pl.col("nationality")
            .map_elements(normalize_nationality, return_dtype=pl.String)
            .alias("normalized_nationality"),
            (pl.col("source_provider") + ":" + pl.col("player_id")).alias("source_key"),
        )
    )
    enrichment_path = data_dir / "enrichment" / "openfootball_players" / "player_metadata.parquet"
    if enrichment_path.exists():
        enrichment = pl.read_parquet(enrichment_path)
        players = players.join(
            enrichment, on=["source_provider", "player_id"], how="left"
        ).with_columns(
            pl.col("birth_date").fill_null(pl.col("openfootball_birth_date")).alias("birth_date")
        )
    else:
        players = players.with_columns(
            pl.lit(None, dtype=pl.String).alias("metadata_matching_method"),
            pl.lit(None, dtype=pl.Float64).alias("metadata_confidence"),
            pl.lit(None, dtype=pl.String).alias("metadata_evidence"),
            pl.lit(None, dtype=pl.String).alias("metadata_source"),
        )
    return players


def _profile_evidence(data_dir: Path) -> tuple[pl.DataFrame, dict[str, set[tuple[int, str]]]]:
    paths = sorted(
        [
            *data_dir.glob("derived/player_seasons_*.parquet"),
            *data_dir.glob("private/derived/player_seasons_*.parquet"),
            *data_dir.glob("private/recent/providers/*.parquet"),
        ]
    )
    profiles = pl.concat([pl.read_parquet(path) for path in paths], how="diagonal_relaxed")
    if "acquisition_complete" in profiles.columns:
        profiles = profiles.filter(
            (pl.col("source_provider") != "api_football")
            | pl.col("acquisition_complete").fill_null(False)
        )
    evidence: dict[str, set[tuple[int, str]]] = defaultdict(set)
    for row in profiles.select(
        "source_provider", "player_id", "season_name", "team_name"
    ).iter_rows(named=True):
        year = season_start_year(row["season_name"])
        team = normalize_team(row["team_name"])
        if year is not None and team:
            team = " ".join(token for token in team.split() if not token.isdigit())
            evidence[f"{row['source_provider']}:{row['player_id']}"].add((year, team))
    return profiles, evidence


def build_identity_and_history(data_dir: Path) -> dict[str, int]:
    output = data_dir / "private" / "canonical_identity"
    output.mkdir(parents=True, exist_ok=True)
    players = _player_records(data_dir)
    profiles, team_evidence = _profile_evidence(data_dir)
    records = players.to_dicts()
    keys = [row["source_key"] for row in records]
    union = UnionFind(keys)
    method_by_pair: dict[frozenset[str], tuple[str, float, str]] = {}

    def merge_group(group: list[dict], method: str, confidence: float, evidence: str) -> None:
        providers = Counter(row["source_provider"] for row in group)
        if any(count > 1 for count in providers.values()):
            return
        for row in group[1:]:
            union.union(group[0]["source_key"], row["source_key"])
            method_by_pair[frozenset((group[0]["source_key"], row["source_key"]))] = (
                method,
                confidence,
                evidence,
            )

    by_name_dob: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in records:
        if row["normalized_name"] and row["birth_date"]:
            by_name_dob[(row["normalized_name"], row["birth_date"])].append(row)
    for (name, dob), group in by_name_dob.items():
        if len(group) > 1:
            merge_group(group, "exact_name+dob", 1.0, f"name={name}; dob={dob}")

    by_name_nation: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in records:
        if (
            row["normalized_name"]
            and len(row["normalized_name"].split()) >= 2
            and row["normalized_nationality"]
        ):
            by_name_nation[(row["normalized_name"], row["normalized_nationality"])].append(row)
    for (name, nation), group in by_name_nation.items():
        known_dobs = {row["birth_date"] for row in group if row["birth_date"]}
        if len(group) <= 1 or len(known_dobs) > 1:
            continue
        shared_team_seasons = set.intersection(
            *(team_evidence.get(row["source_key"], set()) for row in group)
        )
        if shared_team_seasons:
            merge_group(
                group,
                "exact_name+nationality+team_season",
                0.98,
                f"name={name}; nationality={nation}; team_season={sorted(shared_team_seasons)}",
            )

    clusters: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        clusters[union.find(row["source_key"])].append(row)
    prior: dict[str, str] = {}
    prior_path = output / "player_identity_links.parquet"
    if prior_path.exists():
        for row in (
            pl.read_parquet(prior_path)
            .select("source_key", "canonical_player_id")
            .iter_rows(named=True)
        ):
            prior[row["source_key"]] = row["canonical_player_id"]

    link_rows: list[dict] = []
    for root, cluster in clusters.items():
        existing_ids = sorted(
            {prior[row["source_key"]] for row in cluster if row["source_key"] in prior}
        )
        canonical_player_id = (
            existing_ids[0]
            if existing_ids
            else canonical_id("canonical_player", "scoutprint", root)
        )
        birth_dates = sorted({row["birth_date"] for row in cluster if row["birth_date"]})
        nationalities = sorted({row["nationality"] for row in cluster if row["nationality"]})
        merged = len(cluster) > 1
        for row in cluster:
            method, confidence, evidence = "provider_native", 1.0, row["source_key"]
            if merged:
                pair_evidence = next(
                    (
                        value
                        for pair, value in method_by_pair.items()
                        if row["source_key"] in pair and any(key in pair for key in keys)
                    ),
                    ("transitive_conservative_match", 0.92, "linked through accepted cluster"),
                )
                method, confidence, evidence = pair_evidence
            link_rows.append(
                {
                    **row,
                    "canonical_player_id": canonical_player_id,
                    "canonical_birth_date": birth_dates[0] if len(birth_dates) == 1 else None,
                    "canonical_nationality": " | ".join(nationalities) or None,
                    "matching_method": method,
                    "confidence": confidence,
                    "evidence": evidence,
                    "match_status": "matched_cross_provider" if merged else "provider_native",
                }
            )
    links = pl.DataFrame(link_rows, infer_schema_length=None)
    links.write_parquet(prior_path, compression="zstd")

    linked_pairs = {row["source_key"]: row["canonical_player_id"] for row in link_rows}
    unresolved_rows: list[dict] = []
    by_name: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        if row["normalized_name"]:
            by_name[row["normalized_name"]].append(row)
    for name, group in by_name.items():
        canonical_ids = {linked_pairs[row["source_key"]] for row in group}
        providers = {row["source_provider"] for row in group}
        if len(providers) > 1 and len(canonical_ids) > 1:
            unresolved_rows.append(
                {
                    "normalized_name": name,
                    "source_keys": " | ".join(sorted(row["source_key"] for row in group)),
                    "candidate_canonical_ids": " | ".join(sorted(canonical_ids)),
                    "reason": "exact name exists across providers but corroboration is insufficient or conflicting",
                    "status": "unresolved",
                }
            )
    unresolved = pl.DataFrame(
        unresolved_rows,
        schema={
            "normalized_name": pl.String,
            "source_keys": pl.String,
            "candidate_canonical_ids": pl.String,
            "reason": pl.String,
            "status": pl.String,
        },
    )
    unresolved.write_parquet(output / "unresolved_identity_queue.parquet", compression="zstd")

    join_links = links.select(
        "source_provider",
        "player_id",
        "canonical_player_id",
        "canonical_birth_date",
        "canonical_nationality",
        "matching_method",
        "confidence",
    )
    history = profiles.join(join_links, on=["source_provider", "player_id"], how="left")
    metric_columns = [
        "goals_p90",
        "xg_p90",
        "assists_p90",
        "xa_p90",
        "shots_p90",
        "chance_creation_p90",
        "passes_p90",
        "carries_p90",
        "progressions_p90",
        "defensive_actions_p90",
    ]
    for column in metric_columns:
        if column not in history.columns:
            history = history.with_columns(pl.lit(None, dtype=pl.Float64).alias(column))
    for column in ("age", "nationality", "positions", "team_name"):
        if column not in history.columns:
            history = history.with_columns(pl.lit(None, dtype=pl.String).alias(column))
    history = history.with_columns(
        pl.col("season_name")
        .map_elements(season_start_year, return_dtype=pl.Int64)
        .alias("season_start_year"),
        pl.col("canonical_nationality").fill_null(pl.col("nationality")).alias("nationality"),
        pl.col("competition_name")
        .map_elements(normalize_name, return_dtype=pl.String)
        .str.replace(r"^1 bundesliga$", "bundesliga")
        .alias("competition_key"),
        pl.concat_list([pl.col(column).cast(pl.Float64) for column in metric_columns]).alias(
            "statistical_profile_vector"
        ),
        pl.concat_list(
            [
                pl.col("fp_all_actions"),
                *[pl.col(column).cast(pl.Float64) for column in metric_columns],
            ]
        ).alias("overall_profile_vector"),
    )
    history = history.with_columns(
        pl.struct("canonical_player_id", "competition_key", "season_start_year")
        .map_elements(
            lambda row: canonical_id(
                "player_season",
                "scoutprint",
                "|".join(
                    [
                        str(row["canonical_player_id"]),
                        str(row["competition_key"]),
                        str(row["season_start_year"]),
                    ]
                ),
            ),
            return_dtype=pl.String,
        )
        .alias("player_season_id")
    )

    def age_from_dob(row: dict) -> float | None:
        if row["age"] is not None:
            return float(row["age"])
        if not row["canonical_birth_date"] or row["season_start_year"] is None:
            return None
        born = date.fromisoformat(row["canonical_birth_date"])
        end = date(row["season_start_year"] + 1, 6, 30)
        return round((end - born).days / 365.2425, 1)

    history = history.with_columns(
        pl.struct("age", "canonical_birth_date", "season_start_year")
        .map_elements(age_from_dob, return_dtype=pl.Float64)
        .alias("age"),
        pl.mean_horizontal(
            [pl.col(column).is_not_null().cast(pl.Float64) for column in metric_columns]
        ).alias("statistical_coverage"),
        pl.mean_horizontal(
            [
                pl.col(column).is_not_null().cast(pl.Float64)
                for column in ("age", "nationality", "positions", "team_name")
            ]
        ).alias("metadata_coverage"),
        pl.col("fp_all_actions").is_not_null().cast(pl.Float64).alias("spatial_coverage"),
    ).with_columns(
        (
            pl.col("spatial_coverage") * 0.5
            + pl.col("statistical_coverage") * 0.4
            + pl.col("metadata_coverage") * 0.1
        ).alias("comparison_coverage")
    )
    source_rank = (
        pl.when(pl.col("source_provider") == "impect")
        .then(1)
        .when(pl.col("source_provider") == "statsbomb_open_data")
        .then(2)
        .when(pl.col("source_provider") == "wyscout_public")
        .then(3)
        .when(pl.col("source_provider") == "american_soccer_analysis")
        .then(4)
        .otherwise(5)
    )
    coverage_scope = (
        pl.when(pl.col("source_provider").is_in(["wyscout_public", "impect"]))
        .then(pl.lit("full_league"))
        .when(pl.col("source_provider") == "afriskaut")
        .then(pl.lit("full_competition"))
        .when(pl.col("source_provider") == "american_soccer_analysis")
        .then(pl.lit("full_league"))
        .when(
            (pl.col("source_provider") == "statsbomb_open_data")
            & (pl.col("competition_name") == "La Liga")
            & pl.col("season_start_year").is_between(2016, 2020)
        )
        .then(pl.lit("broad_team_season"))
        .when(
            (pl.col("source_provider") == "statsbomb_open_data")
            & (pl.col("competition_name") == "Ligue 1")
            & pl.col("season_start_year").is_between(2021, 2022)
        )
        .then(pl.lit("broad_team_season"))
        .when(
            (pl.col("source_provider") == "statsbomb_open_data")
            & (pl.col("competition_name") == "Indian Super league")
        )
        .then(pl.lit("broad_league"))
        .when(pl.col("source_provider") == "statsbomb_open_data")
        .then(pl.lit("partial_or_tournament"))
        .otherwise(pl.lit("unknown"))
    )
    history = (
        history.with_columns(
            source_rank.alias("source_preference_rank"),
            coverage_scope.alias("coverage_scope"),
        )
        .with_columns(
            (
                pl.col("coverage_scope").is_in(
                    ["full_league", "full_competition", "broad_league", "broad_team_season"]
                )
                & (pl.col("minutes") >= 450)
                & pl.col("age").is_not_null()
                & (pl.col("statistical_coverage") >= 0.5)
                & (pl.col("spatial_coverage") == 1)
            ).alias("trajectory_eligible"),
            (
                pl.col("coverage_scope").is_in(
                    ["full_league", "full_competition", "broad_league", "broad_team_season"]
                )
                & (pl.col("minutes") >= 450)
                & pl.col("age").is_not_null()
                & (pl.col("statistical_coverage") >= 0.5)
            ).alias("statistical_trajectory_eligible"),
        )
        .sort(
            "canonical_player_id",
            "season_start_year",
            "competition_key",
            "source_preference_rank",
            "comparison_coverage",
            descending=[False, False, False, False, True],
        )
        .with_columns(
            (
                pl.int_range(pl.len()).over(
                    "canonical_player_id", "season_start_year", "competition_key"
                )
                == 0
            ).alias("is_primary_profile")
        )
    )
    history.write_parquet(output / "player_season_history.parquet", compression="zstd")
    return {
        "source_identities": links.height,
        "canonical_players": links["canonical_player_id"].n_unique(),
        "cross_provider_links": links.filter(
            pl.col("match_status") == "matched_cross_provider"
        ).height,
        "unresolved_groups": unresolved.height,
        "player_seasons": history.height,
        "profiles_with_age": history["age"].is_not_null().sum(),
    }
