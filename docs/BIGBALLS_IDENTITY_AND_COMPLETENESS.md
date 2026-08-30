# Big Balls identity and completeness audit

Validated 2026-08-30. The live leaderboard-union collector produced 2,755 source-local rows.
The provider returns player name, team, position and statistics but no durable player ID, DOB or
nationality. Scoutprint therefore retains a deterministic source-local ID and never merges on
name alone.

## Identity classifications

| Status | Rows | Automatic canonical action |
|---|---:|---|
| CONFIRMED | 110 | Linked: unique exact normalized name + team + competition + season match |
| PROBABLE | 58 | Not linked |
| AMBIGUOUS | 5 | Not linked |
| UNRESOLVED | 2,582 | Retained as source-local identities; not linked |

Only CONFIRMED links entered the canonical ledger. Probable, ambiguous and unresolved rows remain
separate. The review and completeness tables are private Parquet state files with field-level
evidence.

## Retrieved player rows by league-season

| League | 2023/24 | 2024/25 | 2025/26 |
|---|---:|---:|---:|
| Premier League | 169 | 171 | 187 |
| La Liga | 186 | 192 | 195 |
| Bundesliga | 182 | 184 | 177 |
| Serie A | 193 | 196 | 196 |
| Ligue 1 | 177 | 173 | 177 |

These counts are the union of seven leaderboards capped at 100 rows per metric; they are not
assumed to be complete rosters. For Bundesliga 2023/24, Big Balls returned 182 of 493 Impect
profiles (36.9%) and 182 of 770 API-Football registered players (23.6%; API-Football includes 486
positive-minute players plus registered/fringe players and a relegation play-off participant).
This demonstrates that Big Balls is a partial enrichment source. The other fourteen denominators
remain pending completed API-Football rosters and must not be labelled full-league coverage.
