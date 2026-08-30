# Status

Updated: 2026-08-30

The recent zero-budget data phase is active. ASA contributes 8,522 Tier C player-seasons, Sportmonks contributes 2,580, Big Balls contributes 2,755 partial enrichment rows, and the validated API-Football Bundesliga smoke adds 770 consolidated Tier C players. The API-Football free account accepts 2023/2024 seasons but rejects 2025; its curated 146-item background queue is active. No UI, Vercel presentation or similarity methodology was changed.

| Phase | State | Verified evidence / remaining work |
|---|---|---|
| 1. Source and licence review | Complete | Official Figshare, StatsBomb, OpenFootball, SkillCorner, SoccerNet and Football-Data pages reviewed; matrix recorded in `DATA_SOURCES.md`. |
| 2. Skeleton and storage | Complete for POC | Python 3.12 packages, raw/normalized/derived split, DuckDB catalogue and Docker image executed. |
| 3. Real vertical slice | Complete | Full England season executed: 380 matches, 514 players, 10,443 appearance records, 595,119 located events and 514 profiles. |
| 4. Spatial engine | Complete for POC | Canonical conversion, tactical zones, typed probability fingerprints and mirror mode; synthetic tests pass. |
| 5. Similarity search | Complete for POC | Exact shortlisted Sinkhorn/cosine/JS blend and robust category scoring; Salah query measured at 5.6s after prefilter. |
| 6. UI | Complete for POC | Search, profile, visual comparison, calculated explanation, coverage, provenance and admin views. In-process test and HTTP health check passed. |
| 7. Multi-league/season | Expanded | Existing Tier A datasets remain intact. ASA adds 8,522 Tier C rows; Sportmonks 2,580; Big Balls 2,755 partial enrichment rows; API-Football's validated Bundesliga 2023/24 smoke adds 770 consolidated provider players. |
| 8. Statistical context | Partial | Per-90 goals, assists, shots, key-pass proxy, passes and defensive events. Wyscout public release lacks xG/carries/receipts. |
| 9. Career trajectory | Recent statistical cohort expanded; score not started | Full identity/history: 17,532 source identities → 16,239 canonical players and 23,829 history rows. The canonical recent table has 17,276 player-seasons / 11,670 players; 3,080 have at least two equivalent recent seasons and 1,563 have all three. Historical 4+ consecutive-season readiness is 147 players. |
| 10. QA/deployment/docs | Complete for current checkpoint | Ruff clean and 38 tests pass. Tests cover caching, priority/queue resume, daily request accounting, source filtering/quarantine, transfer consolidation, null preservation and incomplete-season exclusion. Docker and Vercel were not changed. |

## Published builds

- Source repository: `https://github.com/chrisbushnall-dot/scoutprint`
- Vercel production: `https://scoutprint.vercel.app`
- Vercel static build: 514 player-season profiles; browser similarity search and detailed comparison verified against the production deployment.
- VPS build: Streamlit/DuckDB exact shortlisted Sinkhorn implementation remains available on loopback port 8502.
- Afriskaut is stored only in the VPS raw/normalized/derived data layer; the large raw archive is ignored by Git.

## Explicit limitations

- Big Balls' live leaderboard endpoint supplies no durable provider player ID. Of 2,755 deterministic source-local rows, 110 have unique exact name+team+competition+season corroboration and are confirmed; 58 are probable, 5 ambiguous and 2,582 unresolved. Only confirmed links enter the canonical ledger. Bundesliga 2023/24 completeness is 182/493 (36.9%) against Impect, proving this is partial enrichment rather than a full roster.
- Sportmonks' generic player-statistics filter returned globally unfiltered player pages. Those responses were moved to `data/private/quarantine/` and are excluded from normalization. The corrected season → participating teams → historical squad/player route produced 2,580 validated player-seasons; the free route exposed no xG/xA, so those fields remain null.
- API-Football coverage discovery returned 2,959 catalogue rows across 1,125 competition IDs. The curated accessible matrix selects 73 useful men's competitions / 146 season items for 2023–2024; live requests prove 2025 is blocked. Bundesliga 2023/24 passed the season-team fallback (51 requests, 770 players), while Premier League 2024/25 is blocked because a team needs page 4. Incomplete seasons are excluded and the 92/day queue advances automatically.
- Understat automation is blocked: its live `robots.txt` disallows all paths for all user agents and no affirmative official automation permission was found.

- Afriskaut 2024 supplies a recent discovery population but no provider DOB/age, xG/xA or consecutive seasons, so it does not enable Trajectory Match. Conservative Wikidata enrichment found only 1/857 high-confidence DOB/age match (0.12%), with 11 ambiguous and 845 unmatched.
- Wyscout public event coordinates are not tracking data. They locate recorded actions, not every player at every frame.
- Appearance minutes are derived from published lineup/substitution records and currently assume 90-minute league matches; dismissals require a later refinement.
- Age is calculated at 2018-06-30 when DOB is available.
- Afriskaut season minutes are null when any substitution timestamp cannot be reconciled; 419 of 746 profiles have exact season totals.

## Exact next action

Allow the active API-Football timer to resume at its next 03:35 Europe/Berlin window from Bundesliga 2024 team 167 page 2. Rebuild identity/history after each completed league-season and use completed rosters to fill Big Balls denominators. APIFootball.com is the optional remaining credential because it may uniquely add Championship/Ligue 2 2025/26, which this API-Football free account blocks.
