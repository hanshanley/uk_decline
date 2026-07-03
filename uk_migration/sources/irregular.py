"""Home Office irregular ("illegal") arrivals, including Channel small boats.

Source: "Irregular migration to the UK: detected arrivals via illegal routes" detailed
dataset (``Data_IER_D01``) from the Immigration System Statistics release. We aggregate
detections by calendar year and method of entry -- small boats, inadequately documented
air arrivals, detections at ports, and detections in-country -- plus an ``all`` total.
Data begin in 2018. Partial trailing years are dropped.
"""

from __future__ import annotations

from .. import schema
from .._aggregate import aggregate_by_year
from ._common import fetch_home_office

SOURCE = "Home Office Immigration System Statistics"
ATTACHMENT_PREFIX = "illegal-entry-routes-to-the-uk-dataset-"
SHEET = "Data_IER_D01"

# Column layout of Data_IER_D01 (header on row index 1, so 2 header rows to skip):
# Year, Quarter, Method of entry, Nationality, Region, Sex, Age Group, Number of detections
_YEAR, _QUARTER, _METHOD, _DETECTIONS = 0, 1, 2, 7

_METHODS: dict[str, str] = {
    "Small boat arrivals": "small_boat",
    "Inadequately documented air arrivals": "air",
    "Recorded detections at UK ports": "port",
    "Recorded detections in the UK": "in_country",
}


def _category(row: tuple) -> str | None:
    if len(row) <= _DETECTIONS:
        return None
    return _METHODS.get(row[_METHOD])


def _make_row(year: int, value: float, category: str) -> dict:
    return schema.row(
        period=year,
        metric="irregular_arrivals",
        value=value,
        unit="detections",
        legality=schema.IRREGULAR,
        flow_type=schema.COUNT,
        source=SOURCE,
        category=category,
    )


def parse(rows) -> list[dict]:
    """Aggregate irregular-arrival rows into annual per-method rows plus an ``all`` total."""
    aggregated = aggregate_by_year(
        rows,
        header_rows=2,
        year_idx=_YEAR,
        quarter_idx=_QUARTER,
        value_idx=_DETECTIONS,
        category_of=_category,
    )

    totals: dict[int, float] = {}
    out: list[dict] = []
    for year, category, value in aggregated:
        totals[year] = totals.get(year, 0.0) + value
        out.append(_make_row(year, value, category))
    for year in sorted(totals):
        out.append(_make_row(year, totals[year], "all"))
    return out


def fetch() -> list[dict]:
    """Download the latest irregular-migration dataset and return tidy annual rows."""
    return fetch_home_office(ATTACHMENT_PREFIX, SHEET, parse)
