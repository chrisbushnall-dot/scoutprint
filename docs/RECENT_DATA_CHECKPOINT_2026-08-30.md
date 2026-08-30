# Recent data checkpoint — 2026-08-30

This data-only checkpoint contains 17,276 canonical competition player-seasons for 11,670
canonical players. Provider overlaps are consolidated by canonical player, competition and season;
all source-native rows remain serialized in provenance and metrics are selected by documented
precedence without averaging.

| Equivalent window | Unique players | Player-seasons | Competitions | Tier A | Tier B | Tier C |
|---|---:|---:|---:|---:|---:|---:|
| 2023/24 + calendar 2024 | 6,858 | 7,216 | 14 | 2,068 | 0 | 5,148 |
| 2024/25 + calendar 2025 | 4,336 | 4,630 | 11 | 0 | 0 | 4,630 |
| 2025/26 + calendar 2026 | 4,477 | 4,718 | 11 | 0 | 0 | 4,718 |

Trajectory readiness across equivalent windows is 3,080 players with at least two recent seasons
and 1,563 with all three. The broader historical primary-profile ledger contains 147 players with
at least one run of four consecutive seasons. No trajectory score or UI was implemented.

Current field gaps across the 17,276 recent rows:

- age: 4,499 missing;
- provider xG: 5,999 missing;
- provider xA: 5,999 missing;
- shot/full-event spatial evidence: 14,496 missing;
- 2,780 Tier A rows retain full event fingerprints; no separate Tier B population is currently
  available.

The API-Football queue has reached today's hard 92-request cap and exited. It contains 281 current
items: 20 complete pages, 91 page-ceiling-blocked items across four incomplete 2024 seasons, and
170 currently pending items. The queue expands team pages only after season discovery, so the
known item count is not the final total. The next item is Bundesliga 2024, team 167, page 2. The
timer is enabled for the next 03:35 Europe/Berlin window with randomized delay.
