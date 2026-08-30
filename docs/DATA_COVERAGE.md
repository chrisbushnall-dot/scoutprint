# Scoutprint data coverage

Reviewed 2026-08-30. Counts marked verified were calculated from the released files. Blank cells mean unavailable or not yet measured; they do not mean zero. The machine-readable counterpart is [`DATA_COVERAGE.csv`](DATA_COVERAGE.csv).

## Ingested

| Competition | Season | Source | Tier | Matches | Players | Located events | Age | xG/xA | Status |
|---|---|---|---:|---:|---:|---:|---|---|---|
| Premier League | 2017/18 | Pappalardo/Wyscout | A | 380 | 514 | 595,119 | Yes | No/No | Validated production baseline |
| La Liga | 2017/18 | Pappalardo/Wyscout | A | 380 | 557 | 581,978 | Yes | No/No | Ingested and validated |
| Bundesliga | 2017/18 | Pappalardo/Wyscout | A | 306 | 473 event-active / 472 profiles | 482,162 | Yes | No/No | Ingested and validated; one event-active player has no appearance row |
| Serie A | 2017/18 | Pappalardo/Wyscout | A | 380 | 533 | 600,584 | Yes | No/No | Ingested and validated |
| Ligue 1 | 2017/18 | Pappalardo/Wyscout | A | 380 | 541 | 585,512 | Yes | No/No | Ingested and validated |
| Bundesliga | 2023/24 | Impect | A | 306 | 570 identities / 493 profiles | 922,713 eligible / 939,200 retained | 493/493 profiles | Yes/Yes | Privately ingested and validated; VPS only |
| Selected men's bundle | 2021/22–2024 | StatsBomb Open Data | A | 412 | 3,509 competition player-seasons | 1,406,851 | OpenFootball CC0 enrichment where exact | Provider xG / derived xA | Nine private competition-season selections; partial domestic scopes labelled below |
| La Liga trajectory pilot | 2016/17–2020/21 | StatsBomb Open Data | A | 172 | 1,837 source player-seasons | 656,853 | OpenFootball CC0 enrichment where exact | Provider xG / derived xA | Barcelona-centred broad team seasons; opponents remain partial and ineligible |
| Dynasty Scouting League | 2024 | Afriskaut + Wikidata CC0 experiment | A | 136 | 746 event-active / 837 rostered / 857 total identities | 81,269 eligible / 84,214 retained | 1/857 high-confidence DOB/age | No/No | Ingested; metadata enrichment coverage 0.12% |
| MLS, USLC, USL1, MLS NEXT Pro | 2024 | American Soccer Analysis | C | 1,556 | 2,752 competition player-seasons / 2,485 canonical players | None | 2,710/2,752 | Yes/Yes | Privately ingested; official API |
| MLS, USLC, USL1, MLS NEXT Pro | 2025 | American Soccer Analysis | C | 1,552 | 2,865 competition player-seasons / 2,585 canonical players | None | 2,793/2,865 | Yes/Yes | Privately ingested; official API |
| MLS, USLC, USL1, MLS NEXT Pro | 2026 | American Soccer Analysis | C | 1,143 to date | 2,905 competition player-seasons / 2,673 canonical players | None | 2,759/2,905 | Yes/Yes | Privately ingested; in-progress seasons |
| Top-five leagues | 2023/24 | Big Balls Sports Data | C enrichment | None | 907 partial source-local rows | None | No | Yes/Yes | 110 confirmed links overall; Bundesliga retrieved 182/493 profiles (36.9%) |
| Top-five leagues | 2024/25 | Big Balls Sports Data | C enrichment | None | 916 partial source-local rows | None | No | Yes/Yes | Enrichment only; denominator pending validated broad roster |
| Top-five leagues | 2025/26 | Big Balls Sports Data | C enrichment | None | 932 partial source-local rows | None | No | Yes/Yes | Enrichment only; denominator pending validated broad roster |
| Danish Superliga | 2023/24 | Sportmonks | C | None | 431 | None | 431/431 | No/No | Validated season-bound squads; 359 with minutes |
| Danish Superliga | 2024/25 | Sportmonks | C | None | 419 | None | 413/419 | No/No | Validated season-bound squads; 361 with minutes |
| Danish Superliga | 2025/26 | Sportmonks | C | None | 419 | None | 416/419 | No/No | Validated season-bound squads; 365 with minutes |
| Scottish Premiership | 2023/24 | Sportmonks | C | None | 419 | None | 418/419 | No/No | Validated season-bound squads; 358 with minutes |
| Scottish Premiership | 2024/25 | Sportmonks | C | None | 430 | None | 428/430 | No/No | Validated season-bound squads; 368 with minutes |
| Scottish Premiership | 2025/26 | Sportmonks | C | None | 462 | None | 457/462 | No/No | Validated season-bound squads; 385 with minutes |
| Bundesliga | 2023/24 | API-Football | C | None | 770 consolidated provider players | None | 770/770 | No/No | Complete free-plan team+league pagination; 646 known minutes / 486 positive minutes |

## Clearly licensed and realistically ingestible

| Competition | Season | Source | Tier | Verified scope | Main limitations |
|---|---|---|---:|---|---|
| A-League | 2024/25 | SkillCorner | Experimental tracking/B | 10 matches plus season physical aggregates | Not a season-scale player event population |

## Private/restricted scope and remaining official coverage

StatsBomb match counts below were read from the official `competitions.json` and corresponding match files. A listed competition is not necessarily a complete league season.

| Competition | Season | Matches | Scope warning |
|---|---:|---:|---|
| Bundesliga | 2023/24 | 34 | Bayer Leverkusen matches, not all 306 league fixtures |
| Ligue 1 | 2021/22 | 26 | Partial/team-focused |
| Ligue 1 | 2022/23 | 32 | Partial/team-focused |
| MLS | 2023 | 6 | Sample only |
| Indian Super League | 2021/22 | 115 | Broad release |
| FIFA World Cup | 2022 | 64 | Complete tournament |
| Africa Cup of Nations | 2023 | 52 | Complete tournament |
| Copa America | 2024 | 32 | Complete tournament |
| UEFA Euro | 2024 | 51 | Complete tournament |

Women's releases are deliberately excluded from Scoutprint's acquisition scope.

StatsBomb Open Data is rich Tier A event data and is approved for the same private personal analysis/research layer under its reviewed agreement. Impect supplies 306 Bundesliga 2023/24 matches with event/KPI data and player DOB and is now privately ingested. Both remain excluded from Scoutprint's public asset layer because their agreements restrict raw redistribution and commercial exploitation.

## North-star coverage gap

No reviewed GREEN source provides full-season player-linked spatial data, xG/xA, DOB and consecutive 2022/23–2025/26 seasons across the target men's leagues. ASA now supplies a broad consecutive 2024–2026 Tier C population, but no shot or full-event spatial data. Scoutprint must leave those fields null rather than fabricate them.

API-Football's live `/leagues` catalogue contains 2,959 rows across 1,125 competition IDs for 2023–2025. Live requests show the free account rejects 2025, leaving a curated accessible matrix of 73 men's competitions / 146 season items across 2023–2024. A complete Bundesliga 2023/24 team+league smoke test passed; league-wide pagination alone is unusable because the free plan rejects pages above three. See `API_FOOTBALL_RECENT_ACQUISITION.md`. Sportmonks's corrected season-bound route is complete; its earlier globally unfiltered response remains quarantined and excluded.

The limited Afriskaut Wikidata experiment does not close the age gap: one of 857 identities matched at the required exact-name, nationality and team threshold. Eleven exact-name candidates were retained as ambiguous and were not merged.
