# Recent zero-budget source audit

Reviewed live on 2026-08-30. This records actual endpoint access separately from marketing
claims. Credentials are never written to documentation, logs, cache keys or provenance URLs.

| Source | Policy / access classification | Live target coverage | Current action |
|---|---|---|---|
| Big Balls Sports Data | PRIVATE_GREEN for the private product under the current terms; 1,000 free requests/day | The live coverage endpoint's match-season lists currently report Bundesliga 2024/25 and all top-five leagues for 2025/26; they omit top-five 2023/24 and omit 2024/25 for the other four. Separately, the official xG endpoint documentation claims league-level player history back to 2014. Those rows have no provider player ID, and actual free-key seasons/fields remain unverified. | Public coverage cached with SHA-256. Seven-stat leaderboard-union collector and conservative name/team/season identity mapping are ready; free key required before ingestion. |
| American Soccer Analysis | PRIVATE_GREEN; official unauthenticated API and MIT client | MLS, USL Championship, USL League One and MLS NEXT Pro all returned 2024, 2025 and live 2026 data. | Integrated as Tier C. Every raw response table is privately cached with SHA-256 provenance. |
| API-Football / API-Sports | PRIVATE_GREEN within the official free plan; raw-data resale prohibited | The free plan is 100 requests/day and season entitlements are account-dependent. Exact `/leagues` coverage cannot be established without the project key. | Coverage/queue collectors ready. Daily runner caps itself at 92 requests and checkpoints after every page. |
| Sportmonks | PRIVATE_GREEN within the free subscription | Official plan names Danish Superliga and Scottish Premiership. Exact 2023/24–2025/26 season entitlements require the subscription token. | Coverage and season-player collectors ready; token required. |
| APIFootball.com | PRIVATE_GREEN for private/non-commercial use; resale prohibited | Official free offer names the English Championship and French Ligue 2. Exact three-season entitlement requires the account key. | Coverage and bulk team/player collectors ready; key required. |
| Understat | **BLOCKED** | `https://understat.com/robots.txt` returned `User-agent: *` and `Disallow: /`. No official public API or affirmative automation permission was found. | No scraping, technical validation or collector execution. Written permission would be required. |

## Verified ASA coverage

| League | 2024 matches | 2025 matches | 2026 matches |
|---|---:|---:|---:|
| MLS | 522 | 540 | 327 |
| MLS NEXT Pro | 421 | 421 | 358 |
| USL Championship | 423 | 375 | 269 |
| USL League One | 190 | 216 | 189 |

The 2026 season is in progress, so its counts will change. The normalized table contains player
xG, xA, shots, shots on target, key passes, passing, position, minutes, Goals Added action
categories, DOB, nationality and height where ASA supplies them. Missing fields remain null.

## Provider semantics

ASA `xgoals`, `xassists`, `xpass` and Goals Added remain provider-native metrics. Scoutprint does
not equate them silently with Impect or StatsBomb definitions. No cross-source QA result is
recorded until a genuinely overlapping competition/player-season sample is available.

## Official references

- Big Balls: `https://bigballsdata.com/docs/quickstart`, `https://bigballsdata.com/legal/terms`
- ASA: `https://github.com/American-Soccer-Analysis/itscalledsoccer`
- API-Football: `https://www.api-football.com/pricing/`, `https://www.api-football.com/terms`
- Sportmonks: `https://www.sportmonks.com/football-api/free-football-api/`
- APIFootball.com: `https://apifootball.com/documentation/`, `https://apifootball.com/terms_of_use/`
- Understat policy: `https://understat.com/robots.txt`
