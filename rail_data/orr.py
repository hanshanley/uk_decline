"""Fetch and reshape ORR passenger-rail performance into a tidy London-focused table.

Source: Office of Rail and Road (ORR) Data Portal, **Table 3103 — historic passenger
trains planned, PPM and CaSL by operator** (quarterly, from 1997-98). The ORR does not
publish a *historic* sector aggregate, so we rebuild the **London and South East** sector
(and a **Great Britain** total for context) ourselves by taking each operator's figure
weighted by the number of trains it planned that quarter:

    sector_value = sum(operator_value * trains_planned) / sum(trains_planned)

The operator -> sector membership below reproduces ORR's official "London and South East"
sector to within ~0.2 percentage points on the 2019+ quarters where ORR *does* publish a
sector figure (Table 3113), which validates both the membership set and the weighting.

Two metrics are produced:
  - ``ppm_pct``  — Public Performance Measure: % of trains "on time" (arriving within
    5 min for LSE/regional services). The lenient headline measure.
  - ``casl_pct`` — Cancellations and Significant Lateness: % of trains cancelled or
    significantly late. The disruption measure (higher = worse).
"""

from __future__ import annotations

import datetime as dt
import io
import re
from urllib.parse import urlsplit

import pandas as pd
import requests

ORR_TABLE_3103_URL = (
    "https://dataportal.orr.gov.uk/media/1811/"
    "table-3103-historic-passenger-trains-planned-ppm-and-casl-quarterly-by-operator.ods"
)
SOURCE = ("Office of Rail and Road (ORR) Data Portal, Table 3103 "
          "(historic PPM & CaSL by operator, quarterly)")

# Franchise titles (Table 3103 column "Franchise title") that make up the ORR
# "London and South East" sector. Grouping by franchise title folds operator renames
# (e.g. Connex South Eastern -> South Eastern Trains -> Southeastern) into one series.
# Validated against ORR's official sector figure (Table 3113), 2019+, to within ~0.2pp.
LONDON_SE_FRANCHISES = frozenset({
    "Chiltern Railways",
    "Crossrail",                                          # TfL Rail / Elizabeth line
    "Integrated Kent (formally known as South Eastern)",  # Southeastern
    "London, Tilbury and Southend",                       # c2c
    "South Western",                                      # South West Trains / SWR
    "Thameslink, Southern and Great Northern",            # Govia Thameslink Railway
    "London Overground",
    "Greater Anglia",
    "East Anglia",
    "Gatwick Express",
    "Great Northern",                                     # WAGN
    "Network SouthCentral",                               # Connex South Central / Southern
    "Great Eastern",
    "Anglia",
    "North London Railways",                              # Silverlink
    "Island Line",
    "West Anglia",
})

LONDON_SE = "London and South East"
GREAT_BRITAIN = "Great Britain"

# The three stacked sub-tables inside the workbook: trains planned, PPM %, CaSL %.
_SHEET_TRAINS = "3103a"
_SHEET_PPM = "3103b"
_SHEET_CASL = "3103c"
_HEADER_ROW = 3          # row holding the period labels ("Apr to Jun 1997", ...)
_FRANCHISE_COL = 1       # "Franchise title"
_FIRST_DATA_ROW = 4

_QUARTER_END = {"Apr to Jun": (6, 30), "Jul to Sep": (9, 30),
                "Oct to Dec": (12, 31), "Jan to Mar": (3, 31)}
_QUARTER_INDEX = {"Apr to Jun": 1, "Jul to Sep": 2, "Oct to Dec": 3, "Jan to Mar": 4}


def _ensure_orr_host(url: str) -> None:
    host = (urlsplit(url).hostname or "").lower()
    if not (host == "dataportal.orr.gov.uk" or host.endswith(".orr.gov.uk")):
        raise ValueError(f"refusing to fetch untrusted host: {url!r}")


def download_workbook(url: str = ORR_TABLE_3103_URL, timeout: int = 120) -> dict:
    """Download the ORR ODS workbook and return ``{sheet_name: DataFrame}``."""
    _ensure_orr_host(url)
    resp = requests.get(url, timeout=timeout,
                        headers={"User-Agent": "uk_decline/0.1 (rail performance research)"})
    _ensure_orr_host(resp.url)
    resp.raise_for_status()
    return pd.read_excel(io.BytesIO(resp.content), sheet_name=None, header=None)


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None  # ORR shorthand like "[z]" / "[x]" for not-applicable / suppressed


def _parse_period(label: str) -> tuple[str, int, int, str] | None:
    """('Jan to Mar 2020 [p]') -> (quarter_label, year, quarter_index, iso_date)."""
    m = re.match(r"(Apr to Jun|Jul to Sep|Oct to Dec|Jan to Mar)\s+(\d{4})", str(label))
    if not m:
        return None
    q_label, year = m.group(1), int(m.group(2))
    month, day = _QUARTER_END[q_label]
    return q_label, year, _QUARTER_INDEX[q_label], dt.date(year, month, day).isoformat()


def _weighted_series(trains: pd.DataFrame, values: pd.DataFrame,
                     franchises: frozenset | None) -> list[tuple[str, float]]:
    """Trains-weighted mean of ``values`` per period, over ``franchises`` (all if None)."""
    periods = {j: str(trains.iloc[_HEADER_ROW, j]) for j in range(_FIRST_DATA_ROW, trains.shape[1])
               if str(trains.iloc[_HEADER_ROW, j]) != "nan"}
    out: list[tuple[str, float]] = []
    for j, label in periods.items():
        weight_sum = weighted = 0.0
        for i in range(_FIRST_DATA_ROW, trains.shape[0]):
            if franchises is not None and str(trains.iloc[i, _FRANCHISE_COL]) not in franchises:
                continue
            t = _to_float(trains.iloc[i, j])
            v = _to_float(values.iloc[i, j])
            if t is not None and v is not None:
                weight_sum += t
                weighted += t * v
        if weight_sum:
            out.append((label, weighted / weight_sum))
    return out


def build_rows(workbook: dict | None = None) -> list[dict]:
    """Return tidy rows: one per (region, metric, quarter) for PPM and CaSL."""
    if workbook is None:
        workbook = download_workbook()
    trains = workbook[_SHEET_TRAINS]
    metric_sheets = {"ppm_pct": workbook[_SHEET_PPM], "casl_pct": workbook[_SHEET_CASL]}
    regions = {LONDON_SE: LONDON_SE_FRANCHISES, GREAT_BRITAIN: None}

    rows: list[dict] = []
    for metric, values in metric_sheets.items():
        for region, franchises in regions.items():
            for label, value in _weighted_series(trains, values, franchises):
                parsed = _parse_period(label)
                if parsed is None:
                    continue
                q_label, year, q_index, iso_date = parsed
                rows.append({
                    "region": region,
                    "period": f"{q_label} {year}",
                    "date": iso_date,
                    "year": year,
                    "quarter": q_index,
                    "metric": metric,
                    "value": round(value, 4),
                    "unit": "percent",
                    "source": SOURCE,
                })
    rows.sort(key=lambda r: (r["metric"], r["region"], r["date"]))
    return rows
