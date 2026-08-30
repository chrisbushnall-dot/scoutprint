# API-Football recent acquisition

Validated live on 2026-08-30 with the authenticated free API-Sports account. Raw payloads,
checksums and normalized data remain private.

## Priority matrix

The live `/leagues` catalogue contains 2,959 target-season rows across 1,125 competition IDs.
Scoutprint does not queue all of them. Live entitlement validation showed that this free account
accepts seasons 2022–2024 and rejects 2025, so 2025/26 is explicitly blocked for this source. The
curated men's matrix selects 73 competitions and 146 accessible competition-season discovery items:

| Wave | Competitions | Target-season rows | Scope |
|---|---:|---:|---|
| 1 | 24 | 48 | Explicit high-value leagues, 2024 then 2023 |
| 2 | 27 | 54 | Curated additional men's first divisions |
| 3 | 22 | 44 | Curated second divisions and development leagues |

The matrix excludes 2025 entitlement-blocked rows, cup/youth/women/friendly/play-off rows, rows
without player coverage, and all non-curated catalogue records. Exclusion reasons are stored in
the private matrix.

## Free-plan request-efficiency finding

The league+season player query advertised 39 Bundesliga pages, but the free plan rejects every
`page > 3`. It cannot provide a complete league population. The valid strategy is:

season → participating teams → team + league + season player pages

For Bundesliga 2023/24 this used one team-list request and 50 player pages across 19 provider
participants (the provider includes relegation play-off participant Fortuna Düsseldorf). Every
team query required no more than three pages. A complete provider season therefore costs 51
requests, versus 39 advertised league pages that cannot be traversed on the free plan.

This fallback is validated per competition-season rather than assumed globally. Premier League
2024/25 has at least one team requiring four pages, so that season is marked
`blocked_page_ceiling` and excluded from the canonical recent table; the queue moves to the next
competition instead of ingesting an incomplete population.

The free account also enforces 100 requests/day and 10 requests/minute. Scoutprint uses a hard
92/day ceiling and 6.2-second pacing, leaving diagnostic headroom. Cached pages cost no network
quota. HTTP/transient failures retry conservatively; API-level error payloads are quarantined and
never normalized.

## Validated Bundesliga 2023/24 sample

- 770 provider players after transfer consolidation; 804 team-player rows before consolidation.
- 770 known DOB/age, team and position records.
- 646 with a minutes field; 486 with positive minutes.
- 632 with goals, 349 assists, 399 shots, 492 passing, 433 tackles, 418 dribbling and 482 duels.
- 34 players appeared for more than one provider team and were consolidated to one
  player/competition/season row with all teams retained.
- No xG or xA was exposed; those fields remain NULL.

Cross-source QA against the trusted Impect Bundesliga release found matching season goals for
Harry Kane (36), Jamal Musiala (10), Florian Wirtz (11), Xavi Simons (8) and Victor Boniface (14).
Minutes and assists differ because the providers use different playing-time and assist semantics:
API-Football reports 2,844/1,767/2,382/2,675/1,554 minutes respectively, while Impect records
3,078.0/1,880.0/2,531.6/2,830.9/1,653.6. API-Football assists are 8/5/11/11/8 versus
Impect 9/6/11/14/9. The values are retained separately and are not averaged.

## Background job

`scoutprint-api-football.timer` is enabled for 03:35 Europe/Berlin. The oneshot service reads the
persistent queue, processes cached or highest-priority pending items, checkpoints each response,
normalizes completed pages, and exits at the daily allowance. No agent waits for quota reset.

The first unattended batch ended exactly at 92 requests for the UTC day. Current queue state is
281 items: 20 complete, 91 blocked by page ceiling and 170 pending. Premier League, Championship,
Ligue 1 and Brazil Serie A 2024 are currently blocked as incomplete. The next item is Bundesliga
2024, team 167, page 2. The queue's item count grows as team discovery reveals pages.
