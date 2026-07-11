"""ONS long-run Long-Term International Migration by citizenship group (1964-2015).

This is the historical **International Passenger Survey (IPS)** LTIM series, the only UK
source that reaches back to the 1970s with a nation-of-origin breakdown. ONS discontinued
it when it moved to admin-based estimates, so it is published only as a static archived
ad hoc spreadsheet (old ``.xls`` format, values in thousands) rather than a live data API.
The URL is therefore pinned to that specific archived file.

Citation:
  ONS, "Long-Term International Migration into and out of the UK by citizenship, 1964 to
  2015" (ad hoc 006408), migration timeline data sheets v1.4, December 2016.
  https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/internationalmigration/adhocs/006408longterminternationalmigrationintoandoutoftheukbycitizenship1964to2015

The ``Data`` sheet lays out, per citizenship group, three columns (Immigration,
Emigration, Net Migration); ``-`` marks values not available (e.g. EU sub-groups before
those blocs existed). Values are in thousands and are scaled to people here.
"""

from __future__ import annotations

from .. import schema
from .._http import get_bytes
from .._spreadsheet import read_rows

SOURCE = "ONS Long-Term International Migration (IPS), 1964-2015 [ad hoc 006408]"
_ADHOC = (
    "/peoplepopulationandcommunity/populationandmigration/internationalmigration/adhocs"
    "/006408longterminternationalmigrationintoandoutoftheukbycitizenship1964to2015"
)
FILENAME = "migrationtimelinedatasheetsv1.4december2016.xls"
URL = f"https://www.ons.gov.uk/file?uri={_ADHOC}/{FILENAME}"
SHEET = "Data"

# citizenship group (nation of origin) -> first ("Immigration") column index in the sheet.
# Each group spans three consecutive columns: Immigration, Emigration, Net Migration.
_GROUP_COL: dict[str, int] = {
    "all": 1,
    "british": 4,
    "non_british": 7,
    "eu": 10,
    "eu15": 13,
    "eu8": 16,
    "eu2": 19,
    "non_eu": 22,
}

# offset within a group -> (metric, legality, flow_type)
_MEASURES: list[tuple[int, str, str, str]] = [
    (0, "immigration_by_origin", schema.TOTAL, schema.INFLOW),
    (1, "emigration_by_origin", schema.TOTAL, schema.OUTFLOW),
    (2, "net_migration_by_origin", schema.TOTAL, schema.NET),
]


def _year(cell) -> int | None:
    try:
        year = int(float(cell))
    except (TypeError, ValueError):
        return None
    return year if 1900 <= year <= 2100 else None


def _thousands(cell) -> float | None:
    """Parse a cell of thousands into people, or ``None`` for missing (``-``) values."""
    if isinstance(cell, (int, float)):
        return float(cell) * 1000.0
    if isinstance(cell, str):
        s = cell.strip().replace(",", "")
        if s in {"", "-", ":", "..", "z", "n/a"}:
            return None
        try:
            return float(s) * 1000.0
        except ValueError:
            return None
    return None


def parse(rows) -> list[dict]:
    """Parse the IPS timeline ``Data`` sheet into tidy immigration/emigration/net rows."""
    out: list[dict] = []
    for row in rows:
        if not row:
            continue
        year = _year(row[0])
        if year is None:
            continue
        for group, base in _GROUP_COL.items():
            for offset, metric, legality, flow_type in _MEASURES:
                col = base + offset
                value = _thousands(row[col]) if col < len(row) else None
                if value is None:
                    continue
                out.append(
                    schema.row(
                        period=year,
                        metric=metric,
                        value=value,
                        unit="people",
                        legality=legality,
                        flow_type=flow_type,
                        source=SOURCE,
                        category=group,
                    )
                )
    return out


def fetch() -> list[dict]:
    """Download the archived ONS IPS timeline spreadsheet and return tidy rows."""
    content = get_bytes(URL)
    return parse(read_rows(content, FILENAME, sheet=SHEET))
