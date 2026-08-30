from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from identity.bigballs import classify_bigballs
from ingestion.api_football_normalize import build_provider_table, normalize_player_page
from ingestion.api_football_priority import build_priority_matrix
from ingestion.api_football_queue import initialize_queue, network_requests_today
from ingestion.keyed_recent import normalize_bigballs, normalize_sportmonks
from ingestion.recent import build_recent_player_seasons
from providers.asa import AmericanSoccerAnalysisProvider
from providers.cached_api import CachedJsonClient


def test_cached_client_redacts_credentials_from_public_url(tmp_path: Path) -> None:
    client = CachedJsonClient(
        "test",
        tmp_path,
        usage_class="PRIVATE_GREEN",
        terms_url="https://example.test/terms",
    )
    public = client._public_url(
        "https://example.test/data",
        {"APIkey": "secret", "token": "also-secret", "season": 2025},
    )
    assert "secret" not in public
    assert "season=2025" in public


def test_asa_parquet_safe_preserves_list_columns_and_serializes_dicts() -> None:
    import pandas as pd

    source = pd.DataFrame(
        {
            "season": [{}, "2025"],
            "actions": [[{"action": "Passing"}], []],
        }
    )
    safe = AmericanSoccerAnalysisProvider._parquet_safe(source)
    assert safe["season"].tolist() == ["{}", "2025"]
    assert isinstance(safe.loc[0, "actions"], list)


def test_api_football_queue_is_idempotent_and_prioritized(tmp_path: Path) -> None:
    coverage = pl.DataFrame(
        {
            "league_id": [39, 999],
            "competition": ["Premier League", "Other League"],
            "country": ["England", "Elsewhere"],
            "season": [2025, 2025],
        }
    )
    first = initialize_queue(tmp_path, coverage)
    second = initialize_queue(tmp_path, coverage)
    assert first.height == second.height == 2
    assert second.row(0, named=True)["competition"] == "Premier League"
    assert second.select("league", "season", "page").n_unique() == 2


def test_api_football_priority_matrix_excludes_low_value_competitions(tmp_path: Path) -> None:
    coverage = pl.DataFrame(
        {
            "league_id": [39, 39, 146, 147, 999],
            "competition": [
                "Premier League",
                "Premier League",
                "Super League Women",
                "Cup",
                "Useful First League",
            ],
            "country": ["England", "England", "Belgium", "Belgium", "Example"],
            "season": [2024, 2025, 2025, 2025, 2025],
            "current": [False, True, True, True, True],
            "coverage_json": [json.dumps({"players": True})] * 5,
        }
    )
    matrix = build_priority_matrix(tmp_path, coverage)
    assert matrix.filter((pl.col("league_id") == 39) & (pl.col("season") == 2024))[
        "wave"
    ].item() == 1
    assert (
        matrix.filter((pl.col("league_id") == 39) & (pl.col("season") == 2025))[
            "selected"
        ].item()
        is False
    )
    assert matrix.filter(pl.col("league_id").is_in([146, 147]))["selected"].any() is False
    selected = matrix.filter(pl.col("selected"))
    queue = initialize_queue(tmp_path, selected)
    premier = queue.filter(pl.col("league") == 39)
    assert premier.row(0, named=True)["season"] == 2024


def test_api_football_daily_request_count_includes_only_current_utc_day(tmp_path: Path) -> None:
    root = tmp_path / "private/raw/api_football/test"
    root.mkdir(parents=True)
    (root / "today.json.meta.json").write_text(
        json.dumps({"retrieved_at": "2026-08-30T10:00:00+00:00"})
    )
    (root / "yesterday.json.meta.json").write_text(
        json.dumps({"retrieved_at": "2026-08-29T23:59:59+00:00"})
    )
    now = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    assert network_requests_today(tmp_path, now=now) == 1


def test_recent_table_preserves_provider_values_without_averaging(tmp_path: Path) -> None:
    provider_dir = tmp_path / "private" / "recent" / "providers"
    provider_dir.mkdir(parents=True)
    pl.DataFrame(
        {
            "source_provider": ["official_source"],
            "player_id": ["p1"],
            "competition_name": ["League"],
            "season_name": ["2025"],
            "data_tier": ["C"],
            "provider_xg": [3.25],
        }
    ).write_parquet(provider_dir / "source.parquet")
    counts = build_recent_player_seasons(tmp_path)
    output = pl.read_parquet(tmp_path / "private" / "canonical" / "recent_player_seasons.parquet")
    assert counts["player_seasons"] == 1
    assert output["player_season_id"].null_count() == 0
    assert output["player_season_id"].n_unique() == output.height
    assert output["provider_xg"].item() == 3.25
    assert json.loads(output["metric_provenance_json"].item())["selection"].startswith(
        "provider precedence"
    )


def test_recent_table_excludes_incomplete_api_football_seasons(tmp_path: Path) -> None:
    provider_dir = tmp_path / "private" / "recent" / "providers"
    provider_dir.mkdir(parents=True)
    pl.DataFrame(
        {
            "source_provider": ["api_football", "api_football"],
            "player_id": ["complete", "partial"],
            "competition_name": ["League", "Other League"],
            "season_name": ["2024", "2024"],
            "data_tier": ["C", "C"],
            "acquisition_complete": [True, False],
        }
    ).write_parquet(provider_dir / "api_football.parquet")
    counts = build_recent_player_seasons(tmp_path)
    assert counts["player_seasons"] == 1


def test_api_football_page_normalization_preserves_source_fields(tmp_path: Path) -> None:
    payload = {
        "response": [
            {
                "player": {
                    "id": 7,
                    "name": "Player Seven",
                    "age": 21,
                    "birth": {"date": "2004-01-02"},
                    "nationality": "Testland",
                },
                "statistics": [
                    {
                        "league": {"id": 39, "name": "Premier League", "season": 2025},
                        "team": {"id": 1, "name": "Test FC"},
                        "games": {"appearences": 12, "lineups": 8, "minutes": 800},
                        "goals": {"total": 4, "assists": 2},
                        "shots": {"total": 20, "on": 9},
                        "passes": {"total": 300, "key": 15, "accuracy": "82%"},
                    }
                ],
            }
        ]
    }
    path = normalize_player_page(tmp_path, payload, league_id=39, season=2025, page=1)
    frame = pl.read_parquet(path)
    assert frame["minutes"].item() == 800
    assert frame["pass_accuracy"].item() == 82
    assert frame["provider_xg"].item() is None


def test_api_football_provider_table_consolidates_transfers_and_preserves_nulls(
    tmp_path: Path,
) -> None:
    base = {
        "player": {"id": 7, "name": "Player Seven", "birth": {"date": "2004-01-02"}},
    }
    for page, team, minutes in [(1, "First FC", 500), (2, "Second FC", 300)]:
        payload = {
            "response": [
                {
                    **base,
                    "statistics": [
                        {
                            "league": {"id": 39, "name": "Premier League", "season": 2025},
                            "team": {"id": page, "name": team},
                            "games": {"appearences": 5, "minutes": minutes},
                            "goals": {"total": 1, "assists": None},
                        }
                    ],
                }
            ]
        }
        normalize_player_page(tmp_path, payload, league_id=39, season=2025, page=page)
    output_path = build_provider_table(tmp_path)
    assert output_path is not None
    output = pl.read_parquet(output_path)
    assert output.height == 1
    assert output["minutes"].item() == 800
    assert output["appearances"].item() == 10
    assert output["team_name"].item() == "First FC | Second FC"
    assert output["assists"].item() is None
    assert output["provider_xg"].item() is None


def test_bigballs_union_does_not_duplicate_rankings(tmp_path: Path) -> None:
    root = tmp_path / "private" / "raw" / "bigballs" / "xg_leaders" / "epl" / "2025"
    root.mkdir(parents=True)
    data = {
        "data": {
            "league": {"id": "epl", "name": "Premier League"},
            "season": 2025,
            "leaders": [
                {
                    "player_name": "Example Player",
                    "team": "Example FC",
                    "minutes": 900,
                    "goals": 5,
                    "xg": 4.5,
                    "xa": 2.0,
                }
            ],
        }
    }
    (root / "xg.json").write_text(json.dumps(data))
    (root / "xa.json").write_text(json.dumps(data))
    output = pl.read_parquet(normalize_bigballs(tmp_path))
    assert output.height == 1
    assert output["provider_xg"].item() == 4.5
    assert output["provider_player_id"].item() is None
    assert output["player_id"].item()


def test_sportmonks_normalization_is_season_filtered_and_ignores_quarantine(
    tmp_path: Path,
) -> None:
    root = tmp_path / "private" / "raw" / "sportmonks"
    seasons = root / "coverage" / "seasons"
    seasons.mkdir(parents=True)
    (seasons / "page=1.json").write_text(
        json.dumps(
            {
                "data": [
                    {"id": 25536, "league_id": 271, "name": "2025/2026"},
                ]
            }
        )
    )
    teams = root / "teams" / "season=25536"
    teams.mkdir(parents=True)
    (teams / "page=1.json").write_text(
        json.dumps(
            {"data": [{"id": 10, "name": "Season Team"}, {"id": 20, "name": "Loan Team"}]}
        )
    )
    squads = root / "squads" / "season=25536"
    squads.mkdir(parents=True)
    (squads / "team=10.json").write_text(
        json.dumps(
            {
                "data": [
                    {
                        "player_id": 7,
                        "player": {"id": 7, "display_name": "Valid Player"},
                        "details": [
                            {
                                "type": {"developer_name": "MINUTES_PLAYED"},
                                "value": {"total": 900},
                            }
                        ],
                    }
                ]
            }
        )
    )
    (squads / "team=20.json").write_text(
        json.dumps(
            {
                "data": [
                    {
                        "player_id": 7,
                        "player": {"id": 7, "display_name": "Valid Player"},
                        "details": [
                            {
                                "type": {"developer_name": "MINUTES_PLAYED"},
                                "value": {"total": 100},
                            }
                        ],
                    }
                ]
            }
        )
    )
    quarantine = tmp_path / "private" / "quarantine" / "sportmonks-global"
    quarantine.mkdir(parents=True)
    (quarantine / "page=1.json").write_text(
        json.dumps({"data": [{"player": {"id": 999, "display_name": "Bad Global Player"}}]})
    )

    output = pl.read_parquet(normalize_sportmonks(tmp_path))
    assert output.height == 1
    assert output["provider_player_id"].item() == "7"
    assert output["player_name"].item() == "Valid Player"
    assert output["competition_name"].item() == "Danish Superliga"
    assert output["season_name"].item() == "2025/2026"
    assert output["minutes"].item() == 1000
    assert output["team_name"].item() == "Loan Team | Season Team"


def test_bigballs_identity_classification_never_accepts_name_only() -> None:
    source = pl.DataFrame(
        {
            "source_provider": ["bigballs"] * 4,
            "player_id": ["confirmed", "probable", "ambiguous", "unresolved"],
            "player_name": ["Exact Player", "Moved Player", "Twin Name", "Name Only"],
            "team_name": ["Exact FC", "Old FC", "Twin FC", "Unknown FC"],
            "competition_name": ["Premier League"] * 4,
            "season_name": ["2024"] * 4,
        }
    )
    candidates = pl.DataFrame(
        {
            "source_provider": ["api_football"] * 4,
            "canonical_player_id": ["c1", "c2", "c3", "c4"],
            "player_name": ["Exact Player", "Moved Player", "Twin Name", "Twin Name"],
            "team_name": ["Exact FC", "New FC", "Twin FC", "Twin FC"],
            "competition_name": ["Premier League"] * 4,
            "season_name": ["2024"] * 4,
        }
    )
    result = classify_bigballs(source, candidates).sort("player_id")
    statuses = dict(result.select("player_id", "identity_status").iter_rows())
    assert statuses == {
        "ambiguous": "AMBIGUOUS",
        "confirmed": "CONFIRMED",
        "probable": "PROBABLE",
        "unresolved": "UNRESOLVED",
    }
