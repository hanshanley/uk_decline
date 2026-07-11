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
    "Immigration": ("immigration", schema.TOTAL, schema.INFLOW),
    "Emigration": ("emigration", schema.TOTAL, schema.OUTFLOW),
    "Net migration": ("net_migration", schema.TOTAL, schema.NET),
}

# Table 1 nationality-group columns -> tidy category. The admin-based series reports
# All Nationalities plus British / EU+ / Non-EU+, so we can carry the by-origin split
# forward to the present (the IPS series in ``ons_ips_history`` stops in 2015).
_GROUP_COL: dict[int, str] = {2: "all", 3: "british", 4: "eu", 5: "non_eu"}

# e.g. "YE Dec 24 R" / "YE Dec 25 P" -> year 2024 / 2025. Accept 2- or 4-digit years so a
# future 4-digit ONS label ("YE Dec 2026") is not silently truncated to year 2020.
_YE_DEC = re.compile(r"YE\s+Dec\s+(\d{4}|\d{2})\b")


def _to_year(digits: str) -> int:
    return int(digits) if len(digits) == 4 else 2000 + int(digits)


def parse(rows) -> list[dict]:
    """Parse ONS LTIM Table 1 rows into tidy annual rows by nationality group.

    Emits the ``all`` category plus ``british`` / ``eu`` (EU+) / ``non_eu`` (Non-EU+)
    for each flow, keyed to the ``YE Dec`` (calendar-year) periods.
    """
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
        metric, legality, flow_type = _FLOWS[flow]
        year = _to_year(match.group(1))
        for col, category in _GROUP_COL.items():
            value = row[col] if col < len(row) else None
            if not isinstance(value, (int, float)):
                continue
            out.append(
                schema.row(
                    period=year,
                    metric=metric,
                    value=float(value),
                    unit="people",
                    legality=legality,
                    flow_type=flow_type,
                    source=SOURCE,
                    category=category,
                )
            )
    return out


def fetch() -> list[dict]:
    """Download the latest ONS LTIM spreadsheet and return tidy annual flow rows."""
    url, filename = ons_latest_download(DATASET_PATH)
    content = get_bytes(url)
    return parse(read_rows(content, filename, sheet=SHEET))
