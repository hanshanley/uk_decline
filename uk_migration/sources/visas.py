"""Home Office entry-clearance visas granted, by category (legal migration).

Source: "Outcomes of applications for entry clearance visas" detailed dataset
(``Data_Vis_D02``) from the Immigration System Statistics release. We count visas
**issued** and aggregate by calendar year and "Visa type group": Work, Study, Family,
Visitor, Other. Partial trailing years (fewer than four quarters) are dropped.
"""

from __future__ import annotations

from .. import schema
from .._aggregate import aggregate_by_year
from ._common import fetch_home_office

SOURCE = "Home Office Immigration System Statistics"
ATTACHMENT_PREFIX = "entry-clearance-visa-outcomes-datasets-"
SHEET = "Data_Vis_D02"

# Column layout of Data_Vis_D02 (header on row index 3, so 4 header rows to skip):
# Year, Quarter, Nationality, Region, Visa type group, Visa type, Visa type subgroup,
# Applicant type, Case outcome, Decisions
_YEAR, _QUARTER, _GROUP, _OUTCOME, _DECISIONS = 0, 1, 4, 8, 9


def _category(row: tuple) -> str | None:
    if len(row) <= _DECISIONS:
        return None
    if row[_OUTCOME] != "Issued":
        return None
    group = row[_GROUP]
    return str(group).lower() if group else None


def parse(rows) -> list[dict]:
    """Aggregate visa outcome rows into annual visas-granted-by-category rows."""
    aggregated = aggregate_by_year(
        rows,
        header_rows=4,
        year_idx=_YEAR,
        quarter_idx=_QUARTER,
        value_idx=_DECISIONS,
        category_of=_category,
    )
    return [
        schema.row(
            period=year,
            metric="visas_granted",
            value=value,
            unit="visas issued",
            legality=schema.LEGAL,
            flow_type=schema.COUNT,
            source=SOURCE,
            category=category,
        )
        for year, category, value in aggregated
    ]


def fetch() -> list[dict]:
    """Download the latest entry-clearance visa outcomes dataset and return tidy rows."""
    return fetch_home_office(ATTACHMENT_PREFIX, SHEET, parse)
