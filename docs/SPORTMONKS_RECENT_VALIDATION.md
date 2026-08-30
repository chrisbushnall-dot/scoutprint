# Sportmonks recent ingestion validation

Validated live on 2026-08-30 against the authenticated free subscription. Raw responses and
SHA-256 metadata remain private and Git-ignored.

The production route is strictly season → participating teams → historical squads with embedded
player and season-statistic details. The earlier generic player-statistics response was globally
unfiltered, moved to `data/private/quarantine/`, and is not read by the normalizer.

| Competition | Season | Player-seasons | Known DOB/age | Known minutes | xG | xA |
|---|---:|---:|---:|---:|---:|---:|
| Danish Superliga | 2023/24 | 431 | 431 | 359 | 0 | 0 |
| Danish Superliga | 2024/25 | 419 | 413 | 361 | 0 | 0 |
| Danish Superliga | 2025/26 | 419 | 416 | 365 | 0 | 0 |
| Scottish Premiership | 2023/24 | 419 | 418 | 358 | 0 | 0 |
| Scottish Premiership | 2024/25 | 430 | 428 | 368 | 0 | 0 |
| Scottish Premiership | 2025/26 | 462 | 457 | 385 | 0 | 0 |

Totals: 2,580 competition player-seasons and 1,579 provider players. Transfers are consolidated
to one provider player/competition/season row; team names are retained and numeric team-season
statistics are summed only when present. There are no duplicate provider-player/competition/season
keys. Every selected season returned exactly the twelve participating teams before historical
squad retrieval.

The free entitlement exposed appearances, starts, minutes, goals and assists for subsets of the
season squads plus provider player ID, name, DOB, nationality, position, height and team where
available. It did not expose xG or xA through this route; those fields remain NULL rather than zero.

Sportmonks adds 713 players with at least two target seasons and 283 with all three before any
cross-provider overlap is considered.
