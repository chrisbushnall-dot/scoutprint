from __future__ import annotations

from pathlib import Path

import polars as pl

from ingestion.api_football_normalize import build_provider_table, normalize_player_page
from providers.api_football import ApiFootballProvider


def run_league_season_smoke(
    data_dir: Path, *, league_id: int = 78, season: int = 2023
) -> dict[str, int | str]:
    """Fetch a complete season through teams because free plans reject league pages above 3."""
    provider = ApiFootballProvider(data_dir)
    teams_path = provider.client.raw_dir / f"teams/league={league_id}/season={season}.json"
    teams_cached = teams_path.exists() and teams_path.stat().st_size > 0
    teams_payload = provider.fetch_teams(league_id, season)
    team_ids = sorted({int(item["team"]["id"]) for item in teams_payload.get("response") or []})
    if not team_ids:
        raise RuntimeError("Smoke season returned no participating teams")
    total_pages = 0
    last_results = 0
    network_calls = 0 if teams_cached else 1
    for team_id in team_ids:
        first = provider.fetch_team_player_page(league_id, season, team_id, 1)
        team_pages = int((first.get("paging") or {}).get("total") or 1)
        if team_pages > 3:
            raise RuntimeError(
                f"Team {team_id} needs {team_pages} pages; free entitlement cannot reach all players"
            )
        total_pages += team_pages
        for page in range(1, team_pages + 1):
            path = (
                provider.client.raw_dir
                / f"players/league={league_id}/season={season}/team={team_id}/page={page}.json"
            )
            cached = path.exists() and path.stat().st_size > 0
            payload = (
                first
                if page == 1
                else provider.fetch_team_player_page(league_id, season, team_id, page)
            )
            if not cached:
                network_calls += 1
            paging = payload.get("paging") or {}
            if int(paging.get("current") or page) != page:
                raise RuntimeError(f"API-Football pagination changed for team {team_id} page {page}")
            normalize_player_page(
                data_dir,
                payload,
                league_id=league_id,
                season=season,
                page=team_id * 10 + page,
            )
            if page == team_pages:
                last_results = len(payload.get("response") or [])
    if last_results == 0:
        raise RuntimeError("Final API-Football page was empty; fringe-player pagination not proven")
    provider_table = build_provider_table(data_dir)
    if provider_table is None:
        raise RuntimeError("API-Football provider table was not built")
    frame = pl.read_parquet(provider_table).filter(
        (pl.col("competition_name") == "Bundesliga") & (pl.col("season_name") == str(season))
    )
    if not frame.height or frame["provider_player_id"].is_null().any():
        raise RuntimeError("Smoke output lacks player rows or durable provider IDs")
    state = data_dir / "private/state/api_football_smoke.parquet"
    state.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(state, compression="zstd")
    return {
        "competition": "Bundesliga",
        "season": str(season),
        "teams": len(team_ids),
        "pages": total_pages,
        "network_calls": network_calls,
        "rows": frame.height,
        "unique_players": frame["provider_player_id"].n_unique(),
        "last_page_results": last_results,
    }
