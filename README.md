# Scoutprint

Scoutprint is a self-hosted football recruitment/research proof of concept. It builds player-season probability distributions from event coordinates, combines spatial and per-90 statistical similarity, and shows why two profiles match.

Live dashboard: **https://scoutprint.vercel.app**

Source: **https://github.com/chrisbushnall-dot/scoutprint**

The first real dataset is the CC BY 4.0 Pappalardo/Wyscout 2017/18 Premier League release. It includes Mohamed Salah’s complete league season and is used because StatsBomb Open Data does not publish Premier League 2017/18. See [the source matrix](docs/DATA_SOURCES.md) for the legal/coverage decision.

## What works

- Cached, resumable official Figshare and StatsBomb Open Data downloads with SHA-256 provenance sidecars.
- Provider-isolated parsing, stable canonical IDs and Parquet/DuckDB storage.
- 0–100 spatial coordinates, 16×12 unit-mass player-season fingerprints and interpretable tactical zones.
- All-action, shot, goal, chance-creation, pass and defensive fingerprints where the source supports them.
- Same-side and lateral mirror-role comparison.
- Sinkhorn transport, cosine and Jensen–Shannon spatial metrics with synthetic behaviour tests.
- Configurable similarity categories and a dark Streamlit scouting interface.
- Side-by-side and difference heatmaps, statistical comparison and calculated explanation text.
- Honest coverage and provenance views.

Wyscout 2017/18 does not contain xG, explicit carries, pressures or receipt/touch events. Those remain null/unavailable. StatsBomb can populate several of them for its released competitions.

## Architecture

```text
official download -> data/raw/provider + checksum sidecar
                  -> provider parser
                  -> data/normalized/provider/competition/season/*.parquet
                  -> precomputed data/derived/player_seasons_*.parquet
                  -> DuckDB views -> Streamlit/Plotly
```

The DuckDB file is local and has no network listener. Raw provider files, normalized records and derived features never share a directory.

## Native installation and ingestion

```bash
cd /root/.openclaw/workspace/football-scout
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# Tiny real-data smoke test (12 matches)
python -m scripts.ingest_wyscout --competition England --limit 12

# Full 2017/18 Premier League
python -m scripts.ingest_wyscout --competition England

pytest
streamlit run app/main.py --server.address=127.0.0.1 --server.port=8502
```

Open an SSH tunnel from your own computer:

```bash
ssh -L 8502:127.0.0.1:8502 YOUR_VPS_HOST
```

Then visit `http://127.0.0.1:8502`. A public reverse proxy is intentionally not installed or altered.

## Docker

```bash
cd /root/.openclaw/workspace/football-scout
cp .env.example .env
# Ingest once on the host, or run the ingestion command in a one-off container.
docker compose build
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:8502/_stcore/health
```

The Compose mapping is loopback-only and defaults to host port 8502. Ports 80 and 8080 were already occupied during installation.

## Vercel web deployment

The repository also contains a Vercel-native static dashboard in `web/`. It ships a compact, precomputed CC BY profile snapshot and performs filtering and similarity in the browser. This avoids pretending that Vercel runs the long-lived Streamlit/Docker service.

```bash
source .venv/bin/activate
python -m scripts.export_web_data
vercel link --yes --project scoutprint
vercel deploy --prod
```

The browser build uses projected Earth Mover distance with cosine and Jensen–Shannon similarity for fast all-player search. The local research backend remains the canonical exact shortlisted Sinkhorn implementation; both methods and their distinction are labelled in the interface.

The Vercel project is connected to the GitHub `main` branch, so accepted pushes create production deployments and pull requests create preview deployments.

## Other permitted data

StatsBomb’s 2023/24 competition ID 9/season ID 281 release represents Bayer Leverkusen’s 34 league matches (not a complete 306-match Bundesliga season):

```bash
python -m scripts.ingest_statsbomb --competition 9 --season 281
```

The cron-friendly entry point exists but no cron schedule is created:

```bash
python -m scripts.update_data --competition 9 --season 281
```

## Coordinates and fingerprints

- Canonical pitch: `x=0..100`, `y=0..100`, attacking goal at `x=100`.
- StatsBomb: `x/120×100`, `y/80×100`; its acting-team event frame is already attacking left-to-right.
- Public Wyscout: source is already 0–100 in the acting-team frame.
- Original coordinates and provider source paths are retained on normalized events.
- Each event-type histogram is normalized to mass 1.0; counts/minutes remain separate.
- Pitch mirror mode applies `y → 100-y` to the candidate distribution.

The exact score formula is in [the implementation plan](docs/IMPLEMENTATION_PLAN.md). Spatial similarity is not calculated from rendered images.

## Backups

Stop writes, then copy the data and project metadata. DuckDB views can be rebuilt from Parquet, but the raw and normalized directories preserve reproducibility.

```bash
cd /root/.openclaw/workspace/football-scout
docker compose stop
tar --exclude='./.venv' -czf ../scoutprint-backup-$(date +%F).tar.gz ./data ./docs ./pyproject.toml ./docker-compose.yml ./Dockerfile
docker compose start
```

## Known limitations and next work

- No clearly licensed free source reviewed provides ten continuous recent seasons of dense top-five-league event locations.
- The first release supports the England file. France, Germany, Italy and Spain use the same CC BY collection and are the next adapters/partitions.
- Cross-provider player identity is deliberately not guessed from names.
- Possession, team-strength, league-strength and game-state adjustments are not yet production-ready.
- Dismissal-aware minute reconstruction, parser fixture tests, multi-season trajectory matching and ANN indexing remain later phases.
- Exact Sinkhorn search is appropriate for the initial dataset. Measure before adding approximate search.

## Attribution

The primary proof-of-concept data is from Pappalardo, L. and Massucco, E., “Soccer match event dataset,” Figshare, CC BY 4.0, DOI `10.6084/m9.figshare.c.4415000`. StatsBomb-derived analysis must identify StatsBomb as the source and follow the attribution/logo requirements in its Open Data terms.
