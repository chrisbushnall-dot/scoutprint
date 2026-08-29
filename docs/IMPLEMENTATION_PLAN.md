# Implementation plan

## Architecture decisions

- Streamlit/Plotly application on a single VPS.
- Cached provider-native JSON in `data/raw`; canonical partitioned Parquet in `data/normalized`; player-season features in `data/derived`.
- DuckDB is a catalogue/query layer over Parquet. No database port is exposed.
- Stable UUIDv5 canonical IDs are derived from entity kind, provider and provider ID. Cross-provider entity resolution is a later explicit mapping step; names are never silently treated as identity.
- Provider adapters own downloads and schema interpretation. Spatial analysis only consumes canonical coordinates.
- Default fingerprint grid is 16×12. It retains useful role detail without the sparse-cell instability seen at 24×16 on low-volume event classes.

## Phases

1. **Source/licence matrix:** verify official source records and record rejected/conditional sources.
2. **Skeleton and storage:** Python packages, cached raw files, Parquet partitions, DuckDB catalogue, Docker.
3. **Real vertical slice:** complete Premier League 2017/18 CC BY event release; Salah as validation reference.
4. **Spatial engine:** 0–100 coordinates, left-to-right provider orientation, 16×12 probability grids, tactical zones, same-side and lateral mirror modes.
5. **Similarity search:** Sinkhorn transport plus cosine and Jensen–Shannon; robust-scaled category features; configurable weights.
6. **UI:** search, profile, comparison, coverage, provenance and admin pages.
7. **Coverage expansion:** remaining 2017/18 top-five Wyscout files, then appropriate StatsBomb releases.
8. **Statistical similarity:** add only provider-supported per-90 metrics; contextual adjustment remains labelled experimental.
9. **Career trajectory:** activate when resolved players have two or more loaded seasons.
10. **Quality and deployment:** synthetic spatial tests, parser fixtures, performance measurement, Docker smoke test, backup/runbook.

## Score contract

Spatial distributions have unit mass; event volume is retained independently. For each spatial grid pair:

`spatial = 100 × (0.55 × exp(-SinkhornDistance / 22) + 0.25 × cosine + 0.20 × (1 - JS distance))`

The user-facing score is clipped to 0–100. Same-side compares canonical grids. Mirror-role compares the candidate after `y → 100-y`; role mode uses the better of those scores. Overall similarity is the weighted average of spatial and available statistical categories. Missing metrics are omitted from their feature category; a zero is never invented.

For interactivity, population filters run first. A cosine/Jensen–Shannon prefilter retains the best 80 spatial candidates, then the documented exact Sinkhorn blend ranks that shortlist. On the full 2017/18 Premier League set, a mirrored Salah query at 900 minimum minutes fell from 35.8 seconds to 5.6 seconds on this VPS.

## Operational constraints

- Container port is loopback-only at `127.0.0.1:8502` by default because ports 80 and 8080 are occupied.
- nginx is not modified. A reverse-proxy example may be added after the desired hostname/access policy is known.
- No cron is installed automatically.
- Raw downloads are never silently overwritten; `.part` files make interrupted downloads safe and sidecars retain checksums.
