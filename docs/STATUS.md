# Status

Updated: 2026-09-01 17:45 Europe/Berlin

## Sample-qualified Development and Biggest Risers

- Development no longer subtracts two Current Level values containing different minutes uplifts.
  It now compares only like-for-like role-component percentiles shared by consecutive seasons,
  excludes Current Level's sample and population-size adjustments, and weights the result by the
  weaker of the two season samples.
- Both seasons must contain at least 900 minutes, at least two common role metrics and at least 50%
  common component coverage. Otherwise Development is explicitly unavailable and the player cannot
  enter Biggest Risers. Behavioural role-group changes remain routed to Role Changes.
- Full-population validation removed Igor Thiago 2025/26 from Biggest Risers: his 168-minute 2024/25
  baseline is now reported as insufficient rather than a +73.1 improvement. No scored Development
  record has fewer than 900 minutes in either season. Comparable Development coverage changes from
  4,634 to 2,253 records, leaving 1,302 positive, sample-qualified risers.
- The dossier explains the 900-minute and like-for-like evidence rule, and the private API publishes
  the revised Development definition with the Radar score model. Focused intelligence/VPS tests,
  Ruff, JavaScript syntax and all 21 authenticated proxy/UI contract checks pass.

## Player scout reports and main-population scope

- Every canonical player result in Radar, Players, Role Search, League Explorer and Team Explorer
  now opens one dedicated, deep-linkable player scout report. Replacement Finder keeps its
  comparison interaction and adds an explicit report link; Match Explorer player names resolve to
  the latest canonical report when a match identity is available. Back navigation restores the
  originating product surface and scroll position.
- The report keeps the existing evidence-gated Development, Spatial, Shooting and Creation views,
  and adds a stronger player identity header, a deterministic evidence-led written summary and a
  role-relative percentile profile. The summary is composed only from visible derived season
  evidence and explicitly avoids prediction or transfer-recommendation claims. The layout adapts to
  desktop and 375px mobile widths with keyboard focus and 44px mobile controls preserved.
- MLS NEXT Pro is now outside Scoutprint's main product-intelligence scope. Acquisition remains
  untouched for auditability, but the competition is removed before recent consolidation,
  behavioural roles, percentiles, Current Level, Development, Radar and recruitment populations are
  computed. The VPS loader also applies the boundary defensively to an older snapshot.
- A validated atomic refresh completed at 2026-09-01 15:15:39 Europe/Berlin in 98.702 seconds.
  MLS NEXT Pro fell from 3,105 live recent/intelligence rows to zero while 512 newly normalized
  PitchAPI rows were incorporated concurrently. The resulting live generation contains 25,683
  recent player-seasons / 17,211 canonical recent players and 31,683 full intelligence
  player-seasons / 20,953 people. Recent tiers are 2,780 A, 6,691 B and 16,212 C.
- The intentional-scope-aware non-shrinking gate still compares every eligible live row and does not
  permit unrelated loss. The API hot-loaded the filtered generation with zero container restarts;
  its live catalogue contains no MLS NEXT Pro entry. PitchAPI, Reef and API-Football timers all
  remained enabled and active on their existing schedules.
- Focused validation: Ruff clean; 12 intelligence/refresh tests and 21 authenticated proxy/UI
  contract tests pass; the live API catalogue and a real player lookup both passed.

## Live incremental data refresh

- The host now runs `scoutprint-intelligence-refresh.timer` every five minutes after the previous
  attempt finishes. The timer is installed, enabled, active and reboot-persistent. Each tick hashes
  only completed normalized product inputs, skips unchanged generations and coalesces every atomic
  collector publication since the previous tick into one rebuild. Per-match PitchAPI shards do not
  trigger product rebuilds before their compact provider table is atomically published.
- Refreshes build all derived artifacts in a private staging directory, enforce non-empty,
  non-shrinking, required-column and unique player-season gates, then atomically promote the complete
  artifact set and publish the generation manifest last. Promotion failure restores the full prior
  artifact set. The API keeps the previous in-memory generation until a valid new manifest exists.
- Deterministic failures retain the last-known-good generation and record the exact exception. The
  same failed input signature retries after bounded exponential backoff: 15 minutes initially, up to
  six hours. A changed source generation can proceed immediately. Collector services are independent.
- PitchAPI player-season normalization is incremental at match level and writes immutable/atomic
  match shards plus an atomic compact provider table after each completed collector batch. Located
  shot evidence produces Tier B, stat-only evidence remains Tier C, and Tier A is never inferred from
  partial evidence. Reef heatmaps are also atomically published and promote non-Tier-A matched rows
  to Tier B.
- The latest successful generation (`fc1c86ca…`) completed at 2026-09-01 13:56:51 Europe/Berlin in
  103.727 seconds: 18,292 canonical recent players, 28,142 recent player-seasons (2,780 Tier A,
  6,251 Tier B, 19,111 Tier C), and 34,142 product-intelligence rows. The searchable recent window
  contains 20,082 classified roles, 5,112 Development records, 9,130 source-backed spatial/shot
  records and 281 comparable spatial-change records.
- End-to-end proof used a naturally completed PitchAPI cache, without invoking or stopping a
  collector. Martin Terrier, Ligue 1 2023/24, was absent from the previous live API; normalization
  produced a 1,532-minute Tier B record with 34 located shots, the timer detected and promoted it,
  and the already-running API returned it after in-memory hot-load. API container restart count
  remained zero. Focused Radar, Player and Recruitment queries returned successfully.
- Operational status is available without Codex via
  `.venv/bin/scoutprint-intelligence-status` (add `--json` for machine-readable output).
- Collector timers were not stopped, restarted or modified. At this checkpoint PitchAPI remains
  active with 21,752 complete, 6,468 unavailable, 30,249 pending and one failed item; Reef remains
  active with 523 heatmaps plus one failed and one ambiguous target; API-Football remains active with
  160 complete, 156 pending and 307 page-ceiling-blocked items.

## Product pivot progress

- **Milestone 1 complete — product/navigation pivot:** Radar is now the default authenticated
  landing view; primary navigation is Radar, Players, Recruitment, Teams and Matches. Historical
  similarity is relabelled and retained under Recruitment → Replacement Finder. The remaining
  intelligence surfaces are being filled in contract order against current normalized data.
- Collector verification at pivot resume: the system timers for API-Football, PitchAPI and Reef
  are enabled and waiting between successful independent runs. They were inspected read-only and
  were not stopped, restarted, delayed or used to repeat ingestion.
- **Milestone 2 complete — behaviour and transparent analytics:** a derived-only intelligence
  builder now precomputes the 18-role behaviour taxonomy plus honest Goalkeeper/Unclassified
  states, role evidence/confidence, role-relative Current Level components, comparable consecutive-
  season Development, underlying-vs-output labels, role/spatial changes, and transparent Radar and
  Breakout components. The current build covers 23,276 primary player-seasons / 15,411 people. In
  the three recent windows, 11,659/17,270 have enough behaviour for a classified outfield role,
  11,293 have Current Level, 2,638 Development and 259 spatial-change evidence. Three focused
  calculation tests pass; missing behaviour and spatial evidence remain explicitly unavailable.
- **P02 complete — derived intelligence API:** the private VPS service now validates and loads the
  last-known-good `player_intelligence.parquet` through an explicit read-only runtime path. Its
  authenticated catalogue exposes coverage, role counts, supported Radar modes and sort fields;
  its authenticated player-season endpoint exposes decoded role evidence, Current Level,
  Development, underlying/output, confidence and Radar components without raw event or map data.
  Focused auth/payload tests pass, and a real-table smoke loaded 23,276 player-seasons / 15,411
  people with 3,276 Development and 1,338 spatial-change records across all seasons.
- **P03 complete — focused Radar API:** the authenticated `/radar` endpoint now ranks the nine
  contracted modes from the precomputed intelligence table, supports season, league, age, role,
  position, minutes and confidence filters, validates deterministic pagination and numeric sorting,
  and returns the visible Current Level, Development, change, confidence and Radar/Breakout score
  components without private raw data. The catalogue now exposes filter values. Changed-file Ruff
  and all 13 focused VPS API tests pass; a read-only real-table smoke sampled every mode across
  23,276 rows, including 1,583 positive risers, 3,150 U21 rows and 2,647 underlying-output leads.
- **P04 complete — Radar home UI:** the authenticated default landing view now loads the private
  intelligence catalogue and ranked Radar results for Breakouts, Biggest Risers, U21, Underlying >
  Output and Role Changes. It provides season, league, role, confidence, age and minutes filters,
  server-backed sortable metrics, explicit Current Level/Development/confidence, supported xG/xA,
  minutes, role and spatial change summaries, a dense desktop table and compact mobile cards. The
  proxy remains authenticated and allowlisted. Changed-file JavaScript syntax checks and all 7
  focused Vercel proxy/UI tests pass.
- **P05 complete — player-first Explorer API:** the authenticated `/players` endpoint now searches
  derived intelligence by player and filters by club, league, season, age, role, position, minutes,
  tier and confidence. It deterministically selects the latest eligible season per canonical player
  by default, supports explicit player-season expansion, server-side sorting and pagination, and
  retains profile histories needed by the existing reference picker. Changed-file Ruff and all 14
  focused VPS API tests pass.
- **P06 complete — Player Explorer UI:** the Players surface now searches the player-first API with
  player, club, league, season, age, role, position, minutes, tier and confidence filters, keeps one
  latest eligible season per player by default with explicit season expansion, and provides
  server-backed sorting and bounded pagination. Results render as a dense desktop table and compact
  mobile cards with role, minutes, Current Level, Development, Radar, xG/90, xA/90, tier and
  confidence visible. JavaScript syntax checks, all 8 focused Vercel proxy/UI tests and the focused
  Player Explorer API contract smoke pass.
- **P07 complete — Player Dossier overview:** Player Explorer rows and mobile cards now open an
  authenticated player-season dossier. Its Overview shows season context, transparent evidence
  confidence, behavioural primary/secondary role classification with weighted percentile evidence,
  and role-relative Current Level component percentiles plus visible population and sample
  reliability adjustments. Missing behavioural or component evidence renders an explicit safe
  unavailable state. JavaScript syntax checks, all 10 focused Vercel proxy/UI tests and the focused
  existing VPS intelligence endpoint contract smoke pass.
- **P08 complete — multi-season Player Development:** the authenticated dossier endpoint now
  returns ordered derived intelligence history for the selected canonical player. The working
  Development view shows season-by-season Current Level, comparable movement, minutes, confidence,
  club/league transitions, largest supported xG/xA/minutes changes and behaviour-led role
  evolution. Non-consecutive or non-comparable history remains explicitly unavailable rather than
  zero. Changed-file Ruff and JavaScript syntax checks, all 11 focused Vercel proxy/UI tests and two
  focused VPS dossier contract smokes pass.
- **P09 complete — safe spatial, shooting and creation views:** the authenticated dossier now
  joins availability-gated derived fingerprints and aggregates from the canonical player-season
  profile. Spatial occupation, shot/goal and chance-creation heatmaps render only when their typed
  evidence exists; supported location shares, xG/output and xA/creation metrics remain visible
  independently, with source definitions and explicit unavailable states instead of inferred maps.
  Changed-file Ruff and JavaScript syntax checks, all 12 focused Vercel proxy/UI tests, two focused
  VPS contract tests and a real canonical-table spatial/non-spatial smoke pass.
- **P10 complete — Recruitment Role Search:** the authenticated role-led candidate search filters
  the precomputed intelligence table by behavioural role, league, season, age and minutes, collapses
  candidates to the latest eligible canonical player-season, and supports deterministic ranking by
  Current Level, Development, Role Fit, age or minutes. The dense desktop table and compact mobile
  cards expose the selected role's evidence strength and behaviour coverage while explicitly
  avoiding transfer-suitability, ability or potential claims. Changed-file Ruff and JavaScript
  syntax checks plus focused VPS API and authenticated Vercel proxy/UI contract smokes pass.
- **P11 complete — Recruitment Replacement Finder:** the existing authenticated exact similarity
  workflow now lives as the finished second Recruitment tool. It selects the latest available
  player-season by default, searches only distinct recent canonical players, and keeps functional
  role compatibility, raw profile similarity, exact spatial reranking where evidence exists,
  comparison coverage and confidence visible. Candidate drill-down now explicitly separates Why
  They Fit from Where They Differ and states that fit is descriptive rather than a transfer
  recommendation. JavaScript syntax, the focused authenticated Vercel UI/proxy contracts and the
  focused exact-search VPS smoke pass.
- **P12 complete — League Explorer:** Radar now opens a league-season intelligence surface with
  linked league/season selectors, a minimum-minutes control, nine contracted leaderboards (U21,
  Breakouts, Risers, Attackers, Creators, Progressors, Defenders, Underlying > Output and Role
  Changes), and behavioural role distribution for the selected evidence population. The private
  authenticated endpoint validates league-season combinations, returns bounded precomputed player
  evidence and makes the ranking limitation explicit. Changed-file Ruff and JavaScript syntax,
  the focused VPS endpoint test and all 17 authenticated Vercel proxy/UI contract checks pass.
- **P13 complete — Team Explorer:** Teams now opens a linked league, season and exact club-label
  explorer backed only by precomputed player-season intelligence. It exposes Current Level leaders,
  Breakout leaders, young-player minutes and minutes-ordered behavioural role depth with confidence
  visible, while explicitly withholding recent results, team xG/shot profiles, passing networks and
  tactical or squad-quality claims that current evidence cannot support. The private authenticated
  endpoint validates the team-league-season combination. Changed-file Ruff and JavaScript syntax,
  the focused VPS Team Explorer test and both focused authenticated proxy/UI checks pass.
- **P14 complete — Match Explorer:** Matches now browses 2,504 completed private PitchAPI caches by
  league, date or team and opens an authenticated evidence-bounded match view. Supported shot/xG
  evidence, recorded lineups, provider player statistics, advanced player evidence and pass-network
  windows are projected without private media or raw payloads; maps and network positions explicitly
  avoid tracking or tactical claims. Changed-file Ruff and JavaScript syntax, the focused VPS match
  test, all 20 authenticated Vercel proxy/UI checks and a real-cache detail smoke pass.
- **P15 complete — safe incremental intelligence refresh:** a coalescing systemd path unit watches
  normalized recent-provider and Reef outputs without changing any collector unit. Its isolated
  refresh rebuilds canonical identities/history, consolidated recent player-seasons and product
  intelligence only when input signatures change, under a non-blocking lock and provider
  completeness gates. Staged outputs must be non-empty and non-shrinking before multi-artifact
  promotion; promotion failure rolls every file back to the last-known-good set. Unique exact
  player/league/season Reef evidence can now fill missing 16x12 spatial fingerprints without
  overriding event data or accepting ambiguous identities. The private API notices the atomic
  refresh generation marker and swaps validated history and intelligence in memory without a
  restart. Changed-file Ruff and syntax checks, six focused refresh/Reef tests, a
  215-input/16,916-provider-row check and a read-only 219-row Reef enrichment smoke pass. The
  collector processes were not stopped, restarted or invoked.
- **Live incremental refresh activated:** `scoutprint-intelligence-refresh.path` is now installed,
  enabled and waiting independently of every collector. Provider/heatmap changes are coalesced behind
  a 180-second quiet window; partial files block the build, timestamp-only rewrites of the exhausted
  Reef table do not trigger wasteful rebuilds, and the existing nonblocking lock, staged validation,
  non-shrinking gates, rollback and manifest-last promotion remain intact. The first live run consumed
  295 completed inputs and atomically promoted 25,229 history rows, 18,676 recent player-seasons and
  24,676 intelligence rows / 16,777 players. The running API hot-loaded that generation without a
  restart. Match Explorer now separately watches PitchAPI's completed-batch summary and atomically
  rescans immutable caches; it advanced from 4,243 to 4,304 supported matches while the PitchAPI
  collector continued its scheduled run. Focused Ruff, 24 refresh/API tests and live Radar, Players,
  Role Search, League, Team, match browse/detail smokes pass. PitchAPI, Reef and API-Football units
  were not stopped, paused, restarted or modified.
- **P16 complete — compact mobile primary flows:** the 375px sticky navigation now keeps Radar,
  Players, Recruitment, Teams and Matches visible together; horizontal Radar, Recruitment and
  dossier tabs expose 44px touch targets and automatically reveal the active selection. Primary
  filter controls are touch-sized, the replacement filter sheet is viewport-bounded, long card and
  team labels truncate safely, and match player statistics retain every column in an internal
  horizontal scroller instead of inheriting generic mobile column hiding. Changed-file JavaScript
  syntax checks and all 20 focused authenticated Vercel proxy/UI contract tests pass.
- **P17 complete — private production API validation:** the loopback-only API image was rebuilt from
  checkpoint `c535c9a` and only the `scoutprint-api` service was recreated; no ingestion or collector
  process was invoked or changed. The rebuilt container is healthy and the real-data smoke verified
  the 401/200 authentication boundary, 23,276 intelligence player-seasons / 15,411 people, all nine
  non-empty Radar modes, Players and dossier, Recruitment Role Search, League and Team explorers,
  plus browsing and detail across 2,604 supported match caches. Private payloads remained on the VPS.
- **P18 complete — production deployment:** the four changed public application files were published
  atomically through the established GitHub MCP route to `chrisbushnall-dot/scoutprint:main` at
  release commit `1f36eae`. Vercel deployed that release automatically; the production HTML,
  JavaScript and CSS hashes exactly match checkpoint `129be5c`. Authentication files, Vercel routing,
  the server-side proxy and private-data boundary were unchanged, and Radar is the authenticated
  default product view. No collector or private data file was published or modified.
- **P19 complete — authenticated production smoke:** the deployed product passed a real authenticated
  desktop and 375px mobile browser pass with no console errors. Radar returned populated results for
  all five headline modes; Player Explorer opened a dossier with multi-season Development and a real
  16x12 spatial heatmap; Role Search and Replacement Finder returned distinct candidates; League and
  Team explorers loaded bounded evidence; and match browsing opened a supported detail with shots/xG,
  lineups, player statistics and pass-network positions. All five primary destinations remained
  visible and usable at 375px, Radar used mobile cards, and the unauthenticated production proxy
  returned 401. No product-code fix, collector action or private-data exposure was required.
- **P20 complete — final status and production report:** the product pivot is complete at local
  checkpoint `3f6d4da`; the public release is `1f36eae` at `https://scoutprint.vercel.app`, backed by
  the healthy loopback-only authenticated VPS API. The final contract-shaped report below records
  the verified production surface, evidence boundaries and stop condition. No new product or data
  phase is authorized by this milestone.
- **Atomic build recovery complete:** commit `c8a5353` is intact. The failed monolithic worker was
  disabled and its only post-checkpoint change, an incomplete `vps_api/main.py` API fragment, was
  preserved for the bounded derived-intelligence API job. Product work now advances through the
  persistent `scoutprint-product-queue.json`: one 10–20 minute job, focused smoke validation,
  explicit commit, then the next job. A lightweight supervisor performs recovery inspection before
  any retry and caps each queue item at two attempts. The three collector timers remain independent.
- **Quota interruption recovery complete:** P03–P06 produced no product-code changes before their
  Codex quota stops, so their false failures and attempt counts were cleared; the spurious P07 launch
  was cleared as well. The queue is back to 2 COMPLETE / 18 PENDING with P03 next. The supervisor now
  creates disabled one-shot worker definitions and manually fires each exactly once, disables every
  finished definition, excludes quota exhaustion from normal retry limits, and will not advance past
  a dependency while its retry cooldown is active. This prevents stale failed cron definitions from
  relaunching and guarantees that completion of one atomic job hands off to at most one next job.

The recent zero-budget data checkpoint is safe and the practical scouting search is live. The canonical recent table contains 17,276 player-seasons / 11,670 players (2,780 Tier A, 0 Tier B, 14,496 Tier C); 17,270 consolidated primary player-seasons are searchable. The API-Football unattended collector remains active and resumable with 153 pages pending under its 92-request/day cap. The exact spatial methodology was not changed.

## Final production report

- **Production:** `https://scoutprint.vercel.app` is authenticated and deployed from public release
  `1f36eae`; the deployed HTML, JavaScript and CSS matched local release checkpoint `129be5c` during
  P18 validation. Final local product checkpoint: `3f6d4da`. The private loopback-only VPS API is
  healthy and preserves the Vercel proxy/authentication boundary.
- **Radar:** the authenticated default home returns non-empty **Breakouts, Biggest Risers, U21,
  Underlying > Output, Role Changes, Creators, Scorers, Midfield and Defensive** rankings. Production
  browser smoke covered the five headline modes; private API smoke covered all nine modes and their
  filters/sorts.
- **Roles and coverage:** the derived model supports 18 behavioural outfield roles plus explicit
  Goalkeeper and Unclassified states. The current product table contains 23,276 player-seasons /
  15,411 people; 11,659 of 17,270 recent player-seasons have enough behavioural evidence for an
  outfield role, 11,293 have Current Level, 2,638 have comparable recent-window Development and 259
  have recent-window spatial-change evidence. Missing evidence remains unavailable rather than zero.
- **Players:** player-first search collapses repeated seasons by default and exposes bounded filters,
  sorting and pagination. The dossier provides transparent Overview, ordered Development history,
  role evolution and availability-gated Spatial, Shooting and Creation evidence. Production smoke
  opened a multi-season dossier with a real 16x12 heatmap; unsupported maps render safe empty states.
- **Recruitment and squad fit:** Role Search and Replacement Finder return distinct candidates with
  behavioural role evidence, Current Level/Development, exact spatial reranking where compatible,
  coverage, confidence, Why They Fit and Where They Differ. Team Explorer provides evidence-bounded
  role depth and young-player minutes as the supported squad view; it does not claim transfer
  suitability, squad quality or knowledge of club strategy.
- **League, teams and matches:** League Explorer exposes all nine contracted leaderboards and role
  distribution. Team Explorer exposes Current Level and Breakout leaders, young-player minutes and
  role depth. Match Explorer browses supported private caches and projects score/context, shots/xG,
  lineups, player statistics, advanced evidence and pass-network positions without publishing raw
  payloads or making tracking/tactical claims.
- **Collectors and refresh:** API-Football, PitchAPI and Reef collectors remain independent of the
  product and were not stopped, restarted or invoked during the pivot. The coalescing derived refresh
  uses input signatures, a non-blocking lock, completeness/non-shrinking gates, staged promotion and
  rollback to last-known-good artifacts; the API hot-loads a validated generation without restart.
- **Production checks:** authenticated desktop and 375px mobile flows passed with no console errors;
  all five primary destinations remained visible, core Radar/Players/Recruitment/League/Team/Match
  paths returned real evidence, and the unauthenticated production proxy returned 401. The rebuilt
  private API also passed real-data coverage and endpoint smoke checks.
- **Real limitations:** coverage varies by source and confidence tier; Current Level and Radar are
  transparent evidence composites, not ability, potential or predictions; Development requires
  comparable consecutive seasons; provider positions are supporting evidence only; event locations
  and pass-network positions are not tracking data; missing xG/xA, spatial, age or history evidence
  is not inferred; and team/recruitment views do not make tactical, squad-quality or transfer-strategy
  claims. Private provider data, media and credentials remain off the public deployment.

The new top-ten three-season acquisition phase is prepared. API-Football has advanced to 430
queue items (83 complete, 194 page-ceiling blocked, 153 pending). New credential-safe PitchAPI
and ReefAPI collectors add broad match/player/shot/advanced payloads and credit-bounded season
player heatmaps respectively. Their code and 49-test suite are green; neither new collector is
activated until its free private key is present. See `RECENT_TOP10_INGESTION.md`.

| Phase | State | Verified evidence / remaining work |
|---|---|---|
| 1. Source and licence review | Complete | Official Figshare, StatsBomb, OpenFootball, SkillCorner, SoccerNet and Football-Data pages reviewed; matrix recorded in `DATA_SOURCES.md`. |
| 2. Skeleton and storage | Complete for POC | Python 3.12 packages, raw/normalized/derived split, DuckDB catalogue and Docker image executed. |
| 3. Real vertical slice | Complete | Full England season executed: 380 matches, 514 players, 10,443 appearance records, 595,119 located events and 514 profiles. |
| 4. Spatial engine | Complete for POC | Canonical conversion, tactical zones, typed probability fingerprints and mirror mode; synthetic tests pass. |
| 5. Similarity search | Final recommendation-quality pass complete locally | Fast statistical/vector retrieval covers Tier A/B/C, followed by the existing exact spatial rerank where compatible. Behaviour-led attacking subroles now distinguish box 9, scoring/creative wide forward, second striker, creative 10 and hybrid creator-scorer. Raw Profile Match remains separate; evidence confidence and functional Role Match explicitly adjust REC. |
| 6. UI | Production scouting search complete; one focused filter pending release | Typed reference autocomplete, linked competition/season selection, recent candidate windows, dense list/cards, deterministic REC grades, working filters/sorts, Tier-aware comparison drill-down, preserved back-state and mobile core-column layout are deployed. The final pass adds only an explicit **Include LOW-confidence discoveries** filter; LOW rows are omitted by default. |
| 7. Multi-league/season | Expanded | Existing Tier A datasets remain intact. ASA adds 8,522 Tier C rows; Sportmonks 2,580; Big Balls 2,755 partial enrichment rows; API-Football's validated Bundesliga 2023/24 smoke adds 770 consolidated provider players. |
| 8. Statistical context | Partial | Per-90 goals, assists, shots, key-pass proxy, passes and defensive events. Wyscout public release lacks xG/carries/receipts. |
| 9. Career trajectory | Recent statistical cohort expanded; score not started | Full identity/history: 17,532 source identities → 16,239 canonical players and 23,829 history rows. The canonical recent table has 17,276 player-seasons / 11,670 players; 3,080 have at least two equivalent recent seasons and 1,563 have all three. Historical 4+ consecutive-season readiness is 147 players. |
| 10. QA/deployment/docs | Final quality pass validated locally; production release pending | Ruff clean; 46 Python and 5 Vercel API tests pass (51 total). Regression coverage includes canonical self-exclusion, unique-player collapse, cross-position negatives, wide-forward versus box-9 role fit, evidence/role-adjusted REC, default LOW exclusion, explanations and Tier C spatial integrity. |

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
- Recommendation coverage has natural source-specific bands rather than a smooth continuum. The
  default 40% numerical threshold is retained, but LOW-confidence rows no longer mix into the
  primary list; users must explicitly enable them as discovery leads.

- Afriskaut 2024 supplies a recent discovery population but no provider DOB/age, xG/xA or consecutive seasons, so it does not enable Trajectory Match. Conservative Wikidata enrichment found only 1/857 high-confidence DOB/age match (0.12%), with 11 ambiguous and 845 unmatched.
- Wyscout public event coordinates are not tracking data. They locate recorded actions, not every player at every frame.
- Appearance minutes are derived from published lineup/substitution records and currently assume 90-minute league matches; dismissals require a later refinement.
- Age is calculated at 2018-06-30 when DOB is available.
- Afriskaut season minutes are null when any substitution timestamp cannot be reconciled; 419 of 746 profiles have exact season totals.

## Stop condition

The contracted Scoutprint product pivot is complete through P20. Stop here; do not begin another
data or product phase automatically.
