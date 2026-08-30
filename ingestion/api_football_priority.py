from __future__ import annotations

import json
import re
from pathlib import Path

import polars as pl

WAVE_1_LEAGUES = {
    39: "England Premier League",
    40: "England Championship",
    61: "France Ligue 1",
    71: "Brazil Serie A",
    78: "Germany Bundesliga",
    88: "Netherlands Eredivisie",
    94: "Portugal Primeira Liga",
    98: "Japan J1 League",
    103: "Norway Eliteserien",
    106: "Poland Ekstraklasa",
    113: "Sweden Allsvenskan",
    119: "Denmark Superliga",
    128: "Argentina Liga Profesional",
    135: "Italy Serie A",
    140: "Spain La Liga",
    144: "Belgium Jupiler Pro League",
    179: "Scotland Premiership",
    207: "Switzerland Super League",
    210: "Croatia HNL",
    218: "Austria Bundesliga",
    253: "USA Major League Soccer",
    286: "Serbia Super Liga",
    292: "South Korea K League 1",
    345: "Czech Republic Czech Liga",
}

WAVE_2_LEAGUES = {
    110: "Wales Premier League",
    164: "Iceland top division",
    169: "China Super League",
    188: "Australia A-League",
    197: "Greece Super League",
    203: "Turkey Super Lig",
    235: "Russia Premier League",
    239: "Colombia Primera A",
    242: "Ecuador Liga Pro",
    250: "Paraguay Division Profesional",
    262: "Mexico Liga MX",
    265: "Chile Primera Division",
    268: "Uruguay Primera Division",
    271: "Hungary NB I",
    281: "Peru Primera Division",
    283: "Romania Liga I",
    288: "South Africa PSL",
    301: "United Arab Emirates Pro League",
    305: "Qatar Stars League",
    307: "Saudi Pro League",
    318: "Cyprus 1. Division",
    323: "India Indian Super League",
    332: "Slovakia Super Liga",
    333: "Ukraine Premier League",
    357: "Ireland Premier Division",
    373: "Slovenia 1. SNL",
    383: "Israel Ligat Ha'al",
}

WAVE_3_LEAGUES = {
    62: "France Ligue 2",
    72: "Brazil Serie B",
    79: "Germany 2. Bundesliga",
    89: "Netherlands Eerste Divisie",
    95: "Portugal Segunda Liga",
    99: "Japan J2 League",
    104: "Norway 1. Division",
    107: "Poland I Liga",
    114: "Sweden Superettan",
    120: "Denmark 1st Division",
    129: "Argentina Primera Nacional",
    136: "Italy Serie B",
    141: "Spain Segunda Division",
    145: "Belgium Challenger Pro League",
    180: "Scotland Championship",
    208: "Switzerland Challenge League",
    211: "Croatia First NL",
    219: "Austria 2. Liga",
    255: "USA USL Championship",
    287: "Serbia Prva Liga",
    293: "South Korea K League 2",
    346: "Czech Republic FNL",
}

EXCLUDE_PATTERN = re.compile(
    r"women|women's|femeni|feminin|female|\bu\d{2}\b|under[- ]?\d|youth|reserve|"
    r"friendly|friendlies|cup|trophy|super cup|play[- ]?off|playoffs|qualification|"
    r"olympic|games|regional|provincial|amateur",
    re.IGNORECASE,
)
def _players_supported(value: str) -> bool:
    try:
        coverage = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return False
    return bool(coverage.get("players"))


def build_priority_matrix(data_dir: Path, coverage: pl.DataFrame | None = None) -> pl.DataFrame:
    if coverage is None:
        coverage = pl.read_parquet(data_dir / "private/state/api_football_coverage.parquet")
    rows: list[dict] = []
    for row in coverage.iter_rows(named=True):
        league_id = int(row["league_id"])
        name = str(row["competition"])
        supports_players = _players_supported(row["coverage_json"])
        if int(row["season"]) == 2025:
            wave, selected, reason = None, False, "free plan live validation allows 2022-2024 only"
        elif not supports_players:
            wave, selected, reason = None, False, "coverage flags do not expose player statistics"
        elif league_id in WAVE_1_LEAGUES:
            wave, selected, reason = 1, True, "explicit high-value men's league"
        elif league_id in WAVE_2_LEAGUES:
            wave, selected, reason = 2, True, "curated useful men's first division"
        elif league_id in WAVE_3_LEAGUES:
            wave, selected, reason = 3, True, "curated second division/development league"
        elif EXCLUDE_PATTERN.search(name):
            wave, selected, reason = None, False, "initial exclusion: cup/youth/women/friendly/play-off"
        else:
            wave, selected, reason = None, False, "not in the curated men's scouting waves"
        season_recency = {2025: 0, 2024: 1, 2023: 2}.get(int(row["season"]), 9)
        rows.append(
            {
                **row,
                "wave": wave,
                "selected": selected,
                "exclusion_reason": None if selected else reason,
                "selection_reason": reason if selected else None,
                "priority": (wave * 10_000 + season_recency * 1_000 + league_id)
                if selected and wave
                else None,
            }
        )
    matrix = pl.DataFrame(rows, infer_schema_length=None).sort(
        pl.col("selected").cast(pl.Int8), "priority", descending=[True, False]
    )
    output = data_dir / "private/state/api_football_priority_matrix.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    matrix.write_parquet(output, compression="zstd")
    return matrix
