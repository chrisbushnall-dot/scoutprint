from __future__ import annotations

import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from similarity.search import rank_similar
from visualisation.pitch import heatmap_figure

st.set_page_config(
    page_title="Scoutprint", page_icon="⚽", layout="wide", initial_sidebar_state="expanded"
)
st.markdown(
    """<style>
.stApp {background: radial-gradient(circle at top right,#102c22 0,#07100d 38%);}
[data-testid="stMetric"] {background:#0b1d17;border:1px solid #1b4636;border-radius:12px;padding:14px;}
.block-container {padding-top:1.6rem;} h1,h2,h3 {letter-spacing:-.025em;}
</style>""",
    unsafe_allow_html=True,
)

DATA_DIR = Path(os.getenv("FOOTBALL_SCOUT_DATA_DIR", "data"))
DB_PATH = Path(os.getenv("FOOTBALL_SCOUT_DB", str(DATA_DIR / "football_scout.duckdb")))


@st.cache_data(show_spinner=False)
def load_profiles(database_path: str, modified: float) -> pd.DataFrame:
    del modified
    with duckdb.connect(database_path, read_only=True) as connection:
        return connection.execute("SELECT * FROM player_seasons").fetchdf()


def explain(reference: pd.Series, candidate: pd.Series) -> str:
    comparisons = [
        ("attacking-third activity", "pct_attacking_third"),
        ("penalty-area presence", "pct_penalty_area"),
        ("half-space use", "pct_half_space"),
        ("wide activity", "pct_wide"),
        ("shot volume", "shots_p90"),
        ("chance creation", "chance_creation_p90"),
    ]
    clauses = []
    for label, metric in comparisons:
        a, b = reference.get(metric), candidate.get(metric)
        if pd.isna(a) or pd.isna(b):
            continue
        difference = float(b) - float(a)
        if abs(difference) < max(abs(float(a)) * 0.12, 0.015):
            clauses.append(f"very similar {label}")
        elif difference > 0:
            clauses.append(f"more {label}")
        else:
            clauses.append(f"less {label}")
    available = ", ".join(clauses[:4]) or "a similar overall event distribution"
    return f"{candidate['player_name']} matches {reference['player_name']} through {available}. This text is generated from the displayed season features; unavailable source metrics are excluded."


def profile_charts(row: pd.Series) -> None:
    st.plotly_chart(
        heatmap_figure(
            row["fp_all_actions"], int(row["grid_x"]), int(row["grid_y"]), "All located actions"
        ),
        width="stretch",
    )
    metrics = [
        "pct_attacking_third",
        "pct_penalty_area",
        "pct_half_space",
        "pct_central",
        "pct_wide",
        "box_presence_rate",
    ]
    labels = ["Attacking third", "Penalty area", "Half-spaces", "Central", "Wide", "Box presence"]
    values = [float(row.get(metric, 0) or 0) * 100 for metric in metrics]
    radar = go.Figure(
        go.Scatterpolar(
            r=values + values[:1],
            theta=labels + labels[:1],
            fill="toself",
            line={"color": "#46d88c"},
        )
    )
    radar.update_layout(
        height=410,
        margin={"l": 25, "r": 25, "t": 35, "b": 20},
        paper_bgcolor="#06100d",
        font={"color": "#eaf6f0"},
        polar={
            "bgcolor": "#0b1d17",
            "radialaxis": {"range": [0, max(50, max(values) + 5)], "gridcolor": "#265040"},
        },
    )
    st.plotly_chart(radar, width="stretch")


def search_page(profiles: pd.DataFrame) -> None:
    st.title("Scoutprint")
    st.caption("Player-season similarity from event distributions—not heatmap screenshots.")
    left, right = st.columns([1.05, 2.2])
    with left:
        competition = st.selectbox(
            "Competition", sorted(profiles["competition_name"].dropna().unique())
        )
        season_options = sorted(
            profiles.loc[profiles["competition_name"] == competition, "season_name"].unique(),
            reverse=True,
        )
        season = st.selectbox("Season", season_options)
        selection = profiles[
            (profiles["competition_name"] == competition) & (profiles["season_name"] == season)
        ].sort_values("player_name")
        default = next((i for i, name in enumerate(selection["player_name"]) if "Salah" in name), 0)
        player_name = st.selectbox(
            "Reference player", selection["player_name"].tolist(), index=default
        )
        reference = selection[selection["player_name"] == player_name].iloc[0]
        min_minutes = st.slider(
            "Minimum minutes",
            0,
            int(max(90, profiles["minutes"].max())),
            min(900, int(profiles["minutes"].max())),
            90,
        )
        mirror_mode = st.toggle("Role similarity / mirror mode", value=True)
    with right:
        a, b = st.columns(2)
        with a:
            st.metric(
                "Reference",
                reference["player_name"],
                f"{reference['team_name']} · {reference['season_name']}",
            )
        with b:
            st.metric(
                "Minutes",
                f"{reference['minutes']:.0f}",
                str(reference.get("positions") or "Position unavailable"),
            )
        profile_charts(reference)

    st.subheader("Category weights")
    defaults = {
        "Spatial role": 35,
        "Goal threat": 20,
        "Shooting": 15,
        "Chance creation": 10,
        "Carrying": 10,
        "Passing": 5,
        "Defending": 5,
    }
    columns = st.columns(len(defaults))
    weights = {
        name: columns[i].number_input(name, 0, 100, value, 5)
        for i, (name, value) in enumerate(defaults.items())
    }
    if st.button("FIND SIMILAR PLAYERS", type="primary", width="stretch"):
        with st.spinner("Comparing precomputed player-season fingerprints…"):
            results = rank_similar(
                profiles, reference["player_season_id"], weights, min_minutes, mirror_mode
            )
            st.session_state["results"] = results
            st.session_state["reference_id"] = reference["player_season_id"]
    results = st.session_state.get("results")
    if results is None or st.session_state.get("reference_id") != reference["player_season_id"]:
        return
    columns_to_show = [
        "player_name",
        "team_name",
        "season_name",
        "age",
        "minutes",
        "Overall",
        "Spatial role",
        "Same-side",
        "Mirrored",
        "Goal threat",
        "Chance creation",
    ]
    available = [column for column in columns_to_show if column in results]
    st.dataframe(
        results[available]
        .head(25)
        .style.format(
            {c: "{:.1f}" for c in available if c not in {"player_name", "team_name", "season_name"}}
        ),
        width="stretch",
        hide_index=True,
    )
    candidate_name = st.selectbox("Open comparison", results.head(25)["player_name"].tolist())
    candidate = results[results["player_name"] == candidate_name].iloc[0]
    st.subheader(f"{reference['player_name']} vs {candidate['player_name']}")
    st.info(explain(reference, candidate))
    c1, c2, c3 = st.columns(3)
    c1.metric("Overall", f"{candidate['Overall']:.1f}")
    c2.metric("Same-side spatial", f"{candidate['Same-side']:.1f}")
    c3.metric("Mirrored role", f"{candidate['Mirrored']:.1f}")
    grid_shape = (int(reference["grid_x"]), int(reference["grid_y"]))
    reference_grid = np.asarray(reference["fp_all_actions"]).reshape(grid_shape)
    candidate_grid = np.asarray(candidate["fp_all_actions"]).reshape(grid_shape)
    h1, h2, h3 = st.columns(3)
    h1.plotly_chart(
        heatmap_figure(reference_grid.ravel(), *grid_shape, reference["player_name"]),
        width="stretch",
    )
    h2.plotly_chart(
        heatmap_figure(candidate_grid.ravel(), *grid_shape, candidate["player_name"]),
        width="stretch",
    )
    h3.plotly_chart(
        heatmap_figure(
            (candidate_grid - reference_grid).ravel(), *grid_shape, "Candidate − reference", True
        ),
        width="stretch",
    )
    metric_rows = [
        "goals_p90",
        "assists_p90",
        "shots_p90",
        "chance_creation_p90",
        "passes_p90",
        "defensive_actions_p90",
        "pct_attacking_third",
        "pct_penalty_area",
        "pct_half_space",
        "pct_wide",
    ]
    comparison = pd.DataFrame(
        {
            "Metric": metric_rows,
            reference["player_name"]: [reference.get(m) for m in metric_rows],
            candidate["player_name"]: [candidate.get(m) for m in metric_rows],
        }
    )
    st.dataframe(comparison, width="stretch", hide_index=True)


def coverage_page(profiles: pd.DataFrame) -> None:
    st.title("Data coverage")
    with duckdb.connect(str(DB_PATH), read_only=True) as connection:
        coverage = connection.execute("""SELECT competition_name, season_name, source_provider,
            count(DISTINCT match_id) matches, count(DISTINCT player_id) players,
            count(*) located_events FROM events JOIN matches USING(match_id)
            GROUP BY ALL ORDER BY competition_name, season_name""").fetchdf()
    st.dataframe(coverage, width="stretch", hide_index=True)
    st.warning(
        "Spatial coverage is dataset-specific. A listed competition-season does not imply ten-season continuity."
    )
    st.dataframe(
        profiles.groupby(["competition_name", "season_name", "source_provider"], dropna=False)
        .agg(player_seasons=("player_season_id", "count"), minutes=("minutes", "sum"))
        .reset_index(),
        width="stretch",
        hide_index=True,
    )


def main() -> None:
    if not DB_PATH.exists():
        st.error(
            "No catalogue found. Run `python -m scripts.ingest_wyscout` from the project directory."
        )
        st.stop()
    profiles = load_profiles(str(DB_PATH), DB_PATH.stat().st_mtime)
    page = st.sidebar.radio(
        "Navigate",
        [
            "Search & compare",
            "Player profile",
            "Career development",
            "Data coverage",
            "Sources & provenance",
            "Ingestion status",
        ],
    )
    st.sidebar.caption("Scoutprint · provenance-first POC")
    if page == "Search & compare":
        search_page(profiles)
    elif page == "Player profile":
        st.title("Player-season profile")
        name = st.selectbox(
            "Player-season",
            profiles.sort_values("player_name")["player_name"]
            + " · "
            + profiles.sort_values("player_name")["season_name"],
        )
        row = profiles.sort_values("player_name").iloc[
            list(
                profiles.sort_values("player_name")["player_name"]
                + " · "
                + profiles.sort_values("player_name")["season_name"]
            ).index(name)
        ]
        st.subheader(f"{row['player_name']} · {row['team_name']} · {row['season_name']}")
        profile_charts(row)
    elif page == "Career development":
        st.title("Career development")
        st.info(
            "The trajectory engine becomes active when two or more seasons for a canonical player are loaded. The initial CC BY dataset contains one club season."
        )
    elif page == "Data coverage":
        coverage_page(profiles)
    elif page == "Sources & provenance":
        st.title("Sources & provenance")
        st.markdown((Path("docs/DATA_SOURCES.md")).read_text())
    else:
        st.title("Ingestion / admin status")
        st.code(
            "python -m scripts.ingest_wyscout\npython -m scripts.ingest_statsbomb --competition 9 --season 281 --limit 34\npython -m scripts.update_data"
        )
        st.caption(
            "No cron job is installed automatically. Raw downloads are cached and checksummed alongside their metadata."
        )


if __name__ == "__main__":
    main()
