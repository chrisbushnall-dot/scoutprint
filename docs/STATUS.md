# Status

Updated: 2026-08-29

| Phase | State | Verified evidence / remaining work |
|---|---|---|
| 1. Source and licence review | Complete | Official Figshare, StatsBomb, OpenFootball, SkillCorner, SoccerNet and Football-Data pages reviewed; matrix recorded in `DATA_SOURCES.md`. |
| 2. Skeleton and storage | Complete for POC | Python 3.12 packages, raw/normalized/derived split, DuckDB catalogue and Docker image executed. |
| 3. Real vertical slice | Complete | Full England season executed: 380 matches, 514 players, 10,443 appearance records, 595,119 located events and 514 profiles. |
| 4. Spatial engine | Complete for POC | Canonical conversion, tactical zones, typed probability fingerprints and mirror mode; synthetic tests pass. |
| 5. Similarity search | Complete for POC | Exact shortlisted Sinkhorn/cosine/JS blend and robust category scoring; Salah query measured at 5.6s after prefilter. |
| 6. UI | Complete for POC | Search, profile, visual comparison, calculated explanation, coverage, provenance and admin views. In-process test and HTTP health check passed. |
| 7. Multi-league/season | Pending | Add remaining 2017/18 top-five files, then suitable StatsBomb releases. |
| 8. Statistical context | Partial | Per-90 goals, assists, shots, key-pass proxy, passes and defensive events. Wyscout public release lacks xG/carries/receipts. |
| 9. Career trajectory | Scaffolded | UI explains data requirement; canonical cross-provider resolution and multi-season data needed. |
| 10. QA/deployment/docs | Complete for POC | Lint clean; 11 tests pass; zero duplicate event IDs, invalid coordinates, or fingerprint-mass errors; Docker Compose healthy on `127.0.0.1:8502`; Vercel browser build live at `https://scoutprint.vercel.app`; README/runbook written. |

## Published builds

- Source repository: `https://github.com/chrisbushnall-dot/scoutprint`
- Vercel production: `https://scoutprint.vercel.app`
- Vercel static build: 514 player-season profiles; browser similarity search and detailed comparison verified against the production deployment.
- VPS build: Streamlit/DuckDB exact shortlisted Sinkhorn implementation remains available on loopback port 8502.

## Explicit limitations

- The free CC BY dataset is historical (2017/18), so it cannot answer “current young players” until a current, permitted source is added.
- Wyscout public event coordinates are not tracking data. They locate recorded actions, not every player at every frame.
- Appearance minutes are derived from published lineup/substitution records and currently assume 90-minute league matches; dismissals require a later refinement.
- Age is calculated at 2018-06-30 when DOB is available.
