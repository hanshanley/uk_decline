"""Parse and validate Trussell's official two-row-header XLSX tables."""

from __future__ import annotations

import re
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from .sources import ACCESSED_DATE, CALENDAR_SOURCE, MIDYEAR_SOURCE

Workbook = str | Path | BinaryIO

_METRICS = {
    "Parcels distributed for adults": "adults",
    "Parcels distributed for children": "children",
    "Total parcels distributed": "total",
    "Number of locations": "locations",
}

OUTPUT_COLUMNS = [
    "period_type",
    "year",
    "period_label",
    "start_date",
    "end_date",
    "adults",
    "children",
    "total",
    "locations",
    "change_vs_previous_pct",
    "change_vs_2019_pct",
    "source_url",
    "accessed_date",
]


def _year_from_header(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value).strip()
    if "percentage change" in text.lower():
        return None
    match = re.search(r"\b(20\d{2})\b", text)
    return int(match.group(1)) if match else None


def _parse(
    source: Workbook,
    *,
    period_type: str,
    source_url: str,
) -> pd.DataFrame:
    wide = pd.read_excel(source, sheet_name="Nations and regions", header=[0, 1])
    geography_columns = [
        column
        for column in wide.columns
        if str(column[0]).strip() == "Nation and Region"
    ]
    if len(geography_columns) != 1:
        raise ValueError("expected one Nation and Region column")
    geography_col = geography_columns[0]
    uk = wide.loc[wide[geography_col].astype(str).str.strip() == "United Kingdom"]
    if len(uk) != 1:
        raise ValueError("expected exactly one United Kingdom row")
    uk_row = uk.iloc[0]

    records: dict[int, dict[str, object]] = {}
    for top, metric in wide.columns[1:]:
        metric_name = _METRICS.get(str(metric).strip())
        year = _year_from_header(top)
        if year is None or metric_name is None:
            continue
        value = pd.to_numeric(uk_row[(top, metric)], errors="coerce")
        if pd.isna(value):
            raise ValueError(f"missing UK value for {year} {metric_name}")
        records.setdefault(year, {})[metric_name] = int(value)

    rows = []
    for year, values in sorted(records.items()):
        missing = set(_METRICS.values()) - values.keys()
        if missing:
            raise ValueError(f"missing metrics for {year}: {sorted(missing)}")
        if period_type == "calendar_year":
            label = str(year)
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"
        elif period_type == "midyear_apr_sep":
            label = f"Apr-Sep {year}"
            start_date = f"{year}-04-01"
            end_date = f"{year}-09-30"
        else:
            raise ValueError(f"unknown period type: {period_type}")
        rows.append(
            {
                "period_type": period_type,
                "year": year,
                "period_label": label,
                "start_date": start_date,
                "end_date": end_date,
                **values,
                "source_url": source_url,
                "accessed_date": ACCESSED_DATE,
            }
        )

    frame = pd.DataFrame(rows)
    return add_changes(validate(frame))


def validate(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "period_type",
        "year",
        "period_label",
        "start_date",
        "end_date",
        "adults",
        "children",
        "total",
        "locations",
        "source_url",
        "accessed_date",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("no parcel rows parsed")
    if frame["year"].duplicated().any():
        raise ValueError("duplicate period years")
    numeric = frame[["adults", "children", "total", "locations"]]
    if numeric.isna().any().any() or (numeric < 0).any().any():
        raise ValueError("parcel values must be non-negative numbers")
    mismatch = frame["adults"] + frame["children"] != frame["total"]
    if mismatch.any():
        bad_years = frame.loc[mismatch, "year"].tolist()
        raise ValueError(f"adult + child parcels do not equal total for {bad_years}")
    return frame.sort_values("year").reset_index(drop=True)


def add_changes(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["change_vs_previous_pct"] = frame["total"].pct_change() * 100
    baseline = frame.loc[frame["year"] == 2019, "total"]
    frame["change_vs_2019_pct"] = (
        frame["total"] / int(baseline.iloc[0]) - 1
    ) * 100 if not baseline.empty else float("nan")
    return frame[OUTPUT_COLUMNS]


def parse_calendar_years(source: Workbook) -> pd.DataFrame:
    return _parse(
        source,
        period_type="calendar_year",
        source_url=CALENDAR_SOURCE.url,
    )


def parse_midyear(source: Workbook) -> pd.DataFrame:
    return _parse(
        source,
        period_type="midyear_apr_sep",
        source_url=MIDYEAR_SOURCE.url,
    )
