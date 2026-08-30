# Expanded source and licence assessment

Reviewed 2026-08-30 against official repository records and terms. This is an engineering assessment, not legal advice.

Status meanings:

- **GREEN:** the reviewed licence clearly supports the planned automated download and processing.
- **AMBER:** useful data exists, but the intended hosted/commercial use, retention or redistribution needs written clarification.
- **RED:** the intended bulk collection or product use is prohibited. Do not ingest.

| Priority | Source | Value to Scoutprint | Coverage | Spatial | xG/xA | Age | Multi-season | Licence assessment | Decision |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | [Afriskaut Dynasty Scouting League 2024](https://github.com/Afriskaut/dynasty-scouting-league-2024-open-data) | Recent under-scouted player pool; passes, shots, dribbles, progression and defence with start/end locations | 136 matches, 837 rostered players, 84,214 unique events | Full event coordinates, 497 x 328 | No/No | No | No | **GREEN — Apache 2.0**; repository expressly releases the dataset and requests credit | **Integrated and validated** |
| 2 | [Pappalardo/Wyscout research release](https://doi.org/10.6084/m9.figshare.c.4415000.v5) | Expands historical reference library with the working adapter | Complete 2017/18 big-five leagues plus Euro 2016 and World Cup 2018 | Full event start/end coordinates | No/No | Yes | No | **GREEN — CC BY 4.0** | All five 2017/18 leagues integrated and validated |
| 3 | [Impect Open Data](https://github.com/ImpectAPI/open-data) | Recent men's league events, KPIs, packing, SHOT_XG, EXPECTED_GOAL_ASSISTS and pxT | Full Bundesliga 2023/24, 306 matches | Yes | Yes/Yes, provider definitions retained | Yes | No | **PRIVATE_GREEN:** personal non-commercial analysis/research; redistribution and commercial exploitation prohibited | Privately ingested; never publish raw or bulk derived data |
| 4 | [StatsBomb Open Data](https://github.com/hudl/open-data) | Rich event semantics: shot xG, carries, receipts, pressure and selected 360 | Discontinuous leagues, teams and tournaments through 2025 | Yes | xG; linked-shot xA is explicitly derived | Lineups do not reliably include DOB | Some competitions, uneven | **PRIVATE_GREEN:** personal analysis/research with attribution; redistribution and commercial exploitation restricted | Fixed 412-match men's bundle privately integrated |
| 5 | [SkillCorner Open Data](https://github.com/SkillCorner/opendata) | Tracking, off-ball runs and physical-data engineering fixture | 10 A-League 2024/25 matches plus aggregates | Tracking at 10 fps | No/No | Limited | No | **GREEN — MIT** | Later experimental adapter, not a discovery population |
| 6 | [OpenFootball](https://github.com/openfootball/football.json) | Fixtures/results and competition context | Broad, volunteer-maintained | No | No/No | No | Yes | **GREEN — CC0/public-domain project terms** | Context only; Tier D |
| 7 | [Wikidata](https://www.wikidata.org/wiki/Wikidata:Licensing) | Possible DOB/nationality/identity evidence | Uneven, especially for academy and smaller-league players | No | No/No | Often | Yes | **GREEN — CC0** | Candidate identity evidence only; never silent fuzzy merges |
| 8 | [football-data.org](https://www.football-data.org/) | Registered API for fixtures, tables and current squad metadata including DOB in some competitions | Plan-dependent | No | No/No | Sometimes | Limited | **AMBER:** automated API is permitted within plan/rate limits, but retention/redistribution rights need confirmation | Consider only after written terms clarification |
| 9 | [Football-Data.co.uk](https://www.football-data.co.uk/data.php) | Match results, odds and team totals | Broad historical | No player locations | No/No | No | Yes | **AMBER:** downloadable files but no clear reusable-data licence/bulk grant found | Hold; does not solve discovery profiles |
| 10 | [Understat](https://understat.com/) | Shot locations and xG/xA-like aggregates would be valuable | Major European leagues | Shot locations | Yes/Yes | Limited | Yes | **RED until permission:** no official public API or clear bulk automation/reuse grant identified | Do not scrape or use third-party mirrors as permission |
| 11 | [Fantasy Premier League](https://fantasy.premierleague.com/help/terms) | Current PL player metadata/aggregates | Premier League | No | No/No | Limited | Yes | **RED:** terms prohibit automated extraction and reserve data rights | Do not ingest |
| 12 | Kaggle/GitHub mirrors | Varies | Varies | Varies | Varies | Varies | Varies | Case-by-case; a mirror does not cure missing upstream permission | Use only with verified upstream provenance and licence |
| 13 | [American Soccer Analysis](https://github.com/American-Soccer-Analysis/itscalledsoccer) | Recent xG/xPass/Goals Added statistical discovery profiles | MLS, USLC, USL1 and MLS NEXT Pro, including 2024–2026 | No | Yes/Yes | Yes where supplied | Yes | **PRIVATE_GREEN:** official public API and MIT client; be mindful of compute | Integrated as 8,522 Tier C player-seasons |
| 14 | [Big Balls Sports Data](https://bigballsdata.com/docs/quickstart) | Top-five player aggregates | 2,755 partial leaderboard-union rows; Bundesliga 2023/24 measured at 36.9% of Impect population | No | Yes/Yes | No | Yes | **PRIVATE_GREEN** within current API terms and free quota | Enrichment-only: 110 confirmed canonical links; 58 probable, 5 ambiguous, 2,582 unresolved remain separate |
| 15 | [API-Football](https://www.api-football.com/pricing/) | Broad Tier C identities and statistics | Curated 73 men's competitions / 146 accessible 2023–2024 items; 2025 blocked; Bundesliga smoke complete | No | No xG/xA on validated player route | Yes | Yes | **PRIVATE_GREEN** within free quota; no raw resale | Active 92/day queue; team+league strategy respects the legitimate free page ceiling |
| 16 | [Sportmonks](https://www.sportmonks.com/football-api/free-football-api/) | Danish and Scottish Tier C profiles | 2,580 player-seasons across all six target league-seasons | No | No/No on free squad route | Yes | Yes | **PRIVATE_GREEN** within free subscription | Integrated from season-bound squads; globally unfiltered response quarantined and excluded |
| 17 | [APIFootball.com](https://apifootball.com/documentation/) | Championship and Ligue 2 Tier C profiles | Account entitlement dependent | No | No advertised xG/xA | Yes | Potentially | **PRIVATE_GREEN** for private/non-commercial use; no resale | Collector ready; key required |

## Source-specific findings

### Afriskaut

The published README states that the archive contains event data, player information, match metadata, lineups, starting directions and timing. Direct archive inspection confirmed:

- 136 unique match IDs and 21 team IDs.
- 837 unique roster player IDs; 746 occur in events.
- 84,214 unique event IDs.
- 365 players rostered in at least five matches, 121 in at least ten, and six in at least twenty.
- Event locations and end locations, with documented 497 x 328 coordinates.
- Pass, shot, dribble, ball progression, recovery, interception, tackle, duel, cross and goalkeeper families.

The adapter reconciles substitution metadata against event clocks and leaves unresolved player-season minutes null. Event semantics, coordinate rejection and orientation rules are documented in `AFRISKAUT_ADAPTER.md`. Age and xG/xA remain unavailable.

### Impect

The clarified personal/private/non-commercial Scoutprint use is within the agreement's analysis/research grant. The complete Bundesliga 2023/24 release is integrated under `data/private/`; its raw and bulk derived data are excluded from GitHub and Vercel. Public/commercial use still requires separate permission.

The repository exposes unusually rich player/event/KPI tables, including DOB and preferred leg. Its licence PDF prohibits alteration, redistribution, reproduction, sale/transfer and commercial use of the data. Scoutprint therefore preserves the downloaded source unchanged and exposes only minimum calculated results through the future authenticated personal interface. Any public or commercial use remains permission-gated.

### StatsBomb

The [official repository](https://github.com/hudl/open-data) provides JSON competitions, matches, lineups, events and selected 360 frames. Exact recent match counts are recorded in `DATA_COVERAGE.md`. Coverage must be assessed at match level: for example, Bundesliga 2023/24 has 34 Bayer Leverkusen matches, not the full 306-match league. The licence requires StatsBomb attribution/logo and restricts redistribution and commercial exploitation.

Scoutprint's fixed private men's bundle now contains 412 matches, 1,406,851 located events and 3,509 profiles. Provider shot xG is preserved; pass xA is transparently derived through StatsBomb's `key_pass_id`. Raw and reconstructable/bulk derived assets remain VPS-private.

### SkillCorner

The official repository contains tracking and dynamic-event data for 10 A-League 2024/25 matches and season-level physical/off-ball/passing aggregates. It is MIT-licensed, but ten matches cannot generate reliable season profiles for a discovery search.

## Acquisition rule

A source moves into ingestion only when all of the following are recorded: official URL, licence/terms version, permitted purpose, automated-download method, redistribution rule, raw checksum, coverage scope and field-level provenance. Missing fields remain null/unavailable. No authentication, access control, rate limit or anti-bot protection may be bypassed.
