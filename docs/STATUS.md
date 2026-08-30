# Status

Updated: 2026-08-30

The recent zero-budget data checkpoint is safe and the practical scouting search is live. The canonical recent table contains 17,276 player-seasons / 11,670 players (2,780 Tier A, 0 Tier B, 14,496 Tier C); 17,270 consolidated primary player-seasons are searchable. The API-Football unattended collector remains active and resumable with 170 pages pending under its 92-request/day cap. The exact spatial methodology was not changed.

| Phase | State | Verified evidence / remaining work |
|---|---|---|
| 1. Source and licence review | Complete | Official Figshare, StatsBomb, OpenFootball, SkillCorner, SoccerNet and Football-Data pages reviewed; matrix recorded in `DATA_SOURCES.md`. |
| 2. Skeleton and storage | Complete for POC | Python 3.12 packages, raw/normalized/derived split, DuckDB catalogue and Docker image executed. |
| 3. Real vertical slice | Complete | Full England season executed: 380 matches, 514 players, 10,443 appearance records, 595,119 located events and 514 profiles. |
| 4. Spatial engine | Complete for POC | Canonical conversion, tactical zones, typed probability fingerprints and mirror mode; synthetic tests pass. |
| 5. Similarity search | Production recent search complete | Fast statistical/vector retrieval covers Tier A/B/C, followed by the existing exact spatial rerank where compatible. Missing spatial evidence remains null and comparison coverage is explicit. Salah 2017/18 with 900 minimum minutes returns 4,688 recent candidates in 4.687s in production. |
| 6. UI | Production scouting search complete | Typed reference autocomplete, linked competition/season selection, recent candidate windows, dense list/cards, deterministic REC grades, working filters/sorts, Tier-aware comparison drill-down, preserved back-state and mobile core-column layout are deployed. |
| 7. Multi-league/season | Expanded | Existing Tier A datasets remain intact. ASA adds 8,522 Tier C rows; Sportmonks 2,580; Big Balls 2,755 partial enrichment rows; API-Football's validated Bundesliga 2023/24 smoke adds 770 consolidated provider players. |
| 8. Statistical context | Partial | Per-90 goals, assists, shots, key-pass proxy, passes and defensive events. Wyscout public release lacks xG/carries/receipts. |
| 9. Career trajectory | Recent statistical cohort expanded; score not started | Full identity/history: 17,532 source identities → 16,239 canonical players and 23,829 history rows. The canonical recent table has 17,276 player-seasons / 11,670 players; 3,080 have at least two equivalent recent seasons and 1,563 have all three. Historical 4+ consecutive-season readiness is 147 players. |
| 10. QA/deployment/docs | Complete for current checkpoint | Ruff clean; 39 Python and 4 Vercel API tests pass (43 total). The authenticated Vercel → HTTPS VPS API chain and healthy loopback-only API container were verified in production. |

## Published builds

- Source repository: `https://github.com/chrisbushnall-dot/scoutprint`
- Vercel production: `https://scoutprint.vercel.app`
- Vercel production is authenticated and exposes only derived catalogue/search/comparison responses through server-side routes; private datasets and API credentials remain on the VPS.
- VPS API: healthy loopback-only container on port 8511 behind authenticated HTTPS. The production browser verified reference autocomplete, a 4,688-row Salah recent search, Tier C detail without fake maps, and result-state preservation on return.
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

Stop this milestone. Leave the active API-Football timer to resume unattended from Bundesliga 2024 team 167 page 2 and rebuild identity/history after complete league-seasons. Start no further provider or product phase until separately requested.
