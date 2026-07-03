"""ONS Long-Term International Migration: annual immigration, emigration, net.

Source: ONS "Long-term international immigration, emigration and net migration flows,
provisional" spreadsheet. Table 1 carries a quarterly rolling "year ending" series by
nationality group; we take the ``YE Dec`` rows (year ending December = calendar year) and
the ``All Nationalities`` column to get one annual figure per flow.

These are the headline UK long-term migration flows. ONS switched from the International
Passenger Survey to admin-based estimates in 2023, but continues to publish this series, so
it runs to the present.
"""

from __future__ import annotations

import re

from .. import schema
from .._govuk import ons_latest_download
from .._http import get_bytes
from .._spreadsheet import read_rows

SOURCE = "ONS Long-Term International Migration"
DATASET_PATH = (
    "/peoplepopulationandcommunity/populationandmigration/internationalmigration"
    "/datasets/longterminternationalimmigrationemigrationandnetmigrationflowsprovisional"
)
SHEET = "1"

# ONS "Flow" label -> (metric, legality, flow_type)
_FLOWS: dict[str, tuple[str, str, str]] = {
    "Immigration": ("immigration", schema.LEGAL, schema.INFLOW),
    "Emigration": ("emigration", schema.LEGAL, schema.OUTFLOW),
    "Net migration": ("net_migration", schema.TOTAL, schema.NET),
}

# e.g. "YE Dec 24 R" / "YE Dec 25 P" -> year 2024 / 2025. Accept 2- or 4-digit years so a
# future 4-digit ONS label ("YE Dec 2026") is not silently truncated to year 2020.
_YE_DEC = re.compile(r"YE\s+Dec\s+(\d{4}|\d{2})\b")


def _to_year(digits: str) -> int:
    return int(digits) if len(digits) == 4 else 2000 + int(digits)


def parse(rows) -> list[dict]:
    """Parse ONS LTIM Table 1 rows into tidy annual immigration/emigration/net rows."""
    out: list[dict] = []
    for row in rows:
        if not row or len(row) < 3:
            continue
        flow = row[0]
        period = row[1]
        if flow not in _FLOWS or not isinstance(period, str):
            continue
        match = _YE_DEC.search(period)
        if not match:
            continue
        value = row[2]  # "All Nationalities" column
        if not isinstance(value, (int, float)):
            continue
        metric, legality, flow_type = _FLOWS[flow]
        out.append(
            schema.row(
                period=_to_year(match.group(1)),
                metric=metric,
                value=float(value),
                unit="people",
                legality=legality,
                flow_type=flow_type,
                source=SOURCE,
                category="all",
            )
        )
    return out


def fetch() -> list[dict]:
    """Download the latest ONS LTIM spreadsheet and return tidy annual flow rows."""
    url, filename = ons_latest_download(DATASET_PATH)
    content = get_bytes(url)
    return parse(read_rows(content, filename, sheet=SHEET))
