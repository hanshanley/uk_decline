"""Fetch and reshape ORR passenger-rail performance into a tidy London-focused table.

Source: Office of Rail and Road (ORR) Data Portal, **Table 3103 — historic passenger
trains planned, PPM and CaSL by operator** (quarterly, from 1997-98). The ORR does not
publish a *historic* sector aggregate, so we rebuild the **London and South East** sector
(and a **Great Britain** total for context) ourselves by taking each operator's figure
weighted by the number of trains it planned that quarter:

    sector_value = sum(operator_value * trains_planned) / sum(trains_planned)

The operator -> sector membership below is an approximation, not ORR's official sector
aggregate. Across 28 overlapping quarters (Apr-Jun 2019 to Jan-Mar 2026), it differs
from Table 3113 by up to 0.51 percentage points; the reconstructed GB total differs
by up to 0.19 points. Neither reconstruction should be described as exact.

Two metrics are produced:
  - ``ppm_pct``  — Public Performance Measure: % of trains "on time" (arriving within
    5 min for LSE/regional services). The lenient headline measure.
  - ``casl_pct`` — Cancellations and Significant Lateness: % of trains cancelled or
    significantly late. The disruption measure (higher = worse).
"""

from __future__ import annotations

import datetime as dt
import io
import math
import re
from urllib.parse import urlsplit

import pandas as pd
import requests

ORR_TABLE_3103_URL = (
    "https://dataportal.orr.gov.uk/media/1811/"
    "table-3103-historic-passenger-trains-planned-ppm-and-casl-quarterly-by-operator.ods"
)
ORR_TABLE_3113_URL = (
    "https://dataportal.orr.gov.uk/media/1428/"
    "table-3113-public-performance-measure-by-operator-and-sector.ods"
)
SOURCE = ("Office of Rail and Road (ORR) Data Portal, Table 3103 "
          "(historic PPM & CaSL by operator, quarterly)")
OFFICIAL_SOURCE = (
    "Office of Rail and Road (ORR) Data Portal, Table 3113 "
    "(official PPM by operator and sector)"
)

# Franchise titles (Table 3103 column "Franchise title") that make up the ORR
# "London and South East" sector. Grouping by franchise title folds operator renames
# (e.g. Connex South Eastern -> South Eastern Trains -> Southeastern) into one series.
# Approximate membership; see the independent Table 3113 comparison above.
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
_QUARTER_INDEX = {"Apr to Jun": 2, "Jul to Sep": 3, "Oct to Dec": 4, "Jan to Mar": 1}


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
        parsed = float(value)
    except (TypeError, ValueError):
        return None  # ORR shorthand like "[z]" / "[x]" for not-applicable / suppressed
    return parsed if math.isfinite(parsed) else None


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
    if trains.shape != values.shape:
        raise ValueError("ORR trains and metric table shapes differ")
    # Positional weighting is safe only when the operator and period axes agree.
    if not trains.iloc[_HEADER_ROW:, :4].equals(values.iloc[_HEADER_ROW:, :4]):
        raise ValueError("ORR operator rows differ between trains and metric tables")
    if not trains.iloc[_HEADER_ROW, 4:].equals(values.iloc[_HEADER_ROW, 4:]):
        raise ValueError("ORR period columns differ between trains and metric tables")
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
            if t is not None and t > 0 and v is None:
                raise ValueError(
                    f"ORR metric missing for positive planned trains: "
                    f"{trains.iloc[i, _FRANCHISE_COL]}, {label}"
                )
            if t is not None and t > 0 and v is not None:
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


def build_official_rows(workbook: dict | None = None) -> list[dict]:
    """Read published sector PPM and trains-weighted MAA without splicing Table 3103."""
    if workbook is None:
        workbook = download_workbook(ORR_TABLE_3113_URL)
    table = workbook["3113_PPM_(quarterly)"]
    labels = [str(value).strip() for value in table.iloc[:, 0]]
    sections = {}
    for prefix, metric in [("Table 3113a:", "ppm_official_pct"),
                           ("Table 3113b:", "ppm_official_maa_pct")]:
        found = [i for i, label in enumerate(labels) if label.startswith(prefix)]
        if len(found) != 1:
            raise ValueError(f"ORR: missing or duplicate {prefix} section")
        sections[found[0]] = metric
    rows = []
    for start, metric in sorted(sections.items()):
        end = min((i for i in sections if i > start), default=len(table))
        headers = [i for i in range(start + 1, end) if labels[i] == "Time period"]
        if len(headers) != 1:
            raise ValueError(f"ORR: missing or duplicate {metric} header")
        header = headers[0]
        columns = {}
        for region, label in [
            (GREAT_BRITAIN, "Great Britain (percentage)"),
            (LONDON_SE, "London and South East sector (percentage)"),
        ]:
            matches = [i for i, value in enumerate(table.iloc[header]) if str(value) == label]
            if len(matches) != 1:
                raise ValueError(f"ORR: missing or duplicate official {region} column")
            columns[region] = matches[0]
        for i in range(header + 1, end):
            parsed = _parse_period(labels[i])
            if parsed is None:
                continue
            quarter, year, index, date = parsed
            if (metric == "ppm_official_maa_pct"
                    and all(str(table.iloc[i, column]).strip() == "[z]"
                            for column in columns.values())
                    and not any(r["metric"] == metric for r in rows)):
                continue
            for region, column in columns.items():
                value = _to_float(table.iloc[i, column])
                if value is None or not 0 <= value <= 100:
                    raise ValueError(f"ORR: invalid official {region} PPM for {date}")
                rows.append({
                    "region": region, "period": labels[i], "date": date,
                    "year": year, "quarter": index, "metric": metric,
                    "value": round(value, 4), "unit": "percent", "source": OFFICIAL_SOURCE,
                })
    keys = {(r["metric"], r["region"], r["date"]) for r in rows}
    if len(keys) != len(rows):
        raise ValueError("ORR: duplicate official PPM observations")
    coverage = {}
    for metric in sections.values():
        gb = {r["date"] for r in rows if r["metric"] == metric and r["region"] == GREAT_BRITAIN}
        london = {r["date"] for r in rows if r["metric"] == metric and r["region"] == LONDON_SE}
        if not gb or gb != london:
            raise ValueError("ORR: incomplete official PPM sector/quarter coverage")
        coverage[metric] = gb
    quarterly, annual = coverage["ppm_official_pct"], coverage["ppm_official_maa_pct"]
    if not annual <= quarterly or max(annual) != max(quarterly):
        raise ValueError("ORR: incomplete official PPM sector/quarter coverage")
    return sorted(rows, key=lambda r: (r["metric"], r["region"], r["date"]))
