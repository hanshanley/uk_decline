"""Home Office asylum claims (legal migration route).

Source: "Asylum claims" detailed dataset (``Data_Asy_D01``) from the Immigration System
Statistics release. We count claims by **main applicants** (the headline measure, which
avoids double-counting dependants) and aggregate by calendar year. Partial trailing years
are dropped.
"""

from __future__ import annotations

from .. import schema
from .._aggregate import aggregate_by_year
from ._common import fetch_home_office

SOURCE = "Home Office Immigration System Statistics"
ATTACHMENT_PREFIX = "asylum-claims-datasets-"
SHEET = "Data_Asy_D01"

# Column layout of Data_Asy_D01 (header on row index 1, so 2 header rows to skip):
# Year, Quarter, Nationality, Region, Age, Sex, Applicant type, UASC,
# Location of claim, Claims
_YEAR, _QUARTER, _APPLICANT_TYPE, _CLAIMS = 0, 1, 6, 9


def _category(row: tuple) -> str | None:
    if len(row) <= _CLAIMS:
        return None
    return "main_applicant" if row[_APPLICANT_TYPE] == "Main Applicant" else None


def parse(rows) -> list[dict]:
    """Aggregate asylum-claim rows into annual main-applicant claim counts."""
    aggregated = aggregate_by_year(
        rows,
        header_rows=2,
        year_idx=_YEAR,
        quarter_idx=_QUARTER,
        value_idx=_CLAIMS,
        category_of=_category,
    )
    return [
        schema.row(
            period=year,
            metric="asylum_applications",
            value=value,
            unit="claims",
            legality=schema.LEGAL,
            flow_type=schema.COUNT,
            source=SOURCE,
            category=category,
        )
        for year, category, value in aggregated
    ]


def fetch() -> list[dict]:
    """Download the latest asylum claims dataset and return tidy annual rows."""
    return fetch_home_office(ATTACHMENT_PREFIX, SHEET, parse)
