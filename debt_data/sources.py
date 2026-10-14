"""Official UK debt snapshots and OECD monthly government-bond yields."""

from __future__ import annotations

import csv
from datetime import datetime
import io
import math
import re

from bs4 import BeautifulSoup
import pandas as pd
import requests

from europe_data._http import get_text

DEBT_URL = (
    "https://www.ons.gov.uk/economy/governmentpublicsectorandtaxes/"
    "publicsectorfinance/timeseries/hf6x/pusf"
)
ONS_CSV = "https://www.ons.gov.uk/generator"
DEBT_METRIC = "public_sector_net_debt_pct_gdp"
YIELD_METRIC = "government_bond_yield_10y"
YIELD_SERIES = {
    "United Kingdom": "IRLTLT01GBM156N",
    "United States": "IRLTLT01USM156N",
    "Germany": "IRLTLT01DEM156N",
    "France": "IRLTLT01FRM156N",
    "Italy": "IRLTLT01ITM156N",
}
FIELDS = ["date", "country", "metric", "value", "unit", "source", "series_id"]
START = "2000-01-01"


def _number(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Non-finite debt or bond-yield observation: {value!r}")
    return number


def parse_debt(text: str) -> list[dict]:
    records = list(csv.reader(io.StringIO(text)))
    metadata = {row[0]: row[1] for row in records if len(row) == 2}
    if (
        metadata.get("CDID") != "HF6X" or metadata.get("Source dataset ID") != "PUSF"
        or metadata.get("Unit") != "%"
        or "Net Debt (excluding public sector banks)" not in metadata.get("Title", "")
    ):
        raise ValueError("ONS response is not the expected public-sector net-debt/GDP series")
    rows = []
    seen = set()
    for record in records:
        if not record or not re.fullmatch(r"\d{4} [A-Z]{3}", record[0]):
            continue
        if len(record) != 2:
            raise ValueError(f"Malformed ONS monthly debt observation: {record!r}")
        date = datetime.strptime(record[0], "%Y %b").strftime("%Y-%m-%d")
        if date in seen:
            raise ValueError(f"Duplicate ONS monthly debt observation: {date}")
        seen.add(date)
        if record[1] == "" or date < START:
            continue
        rows.append({
            "date": date, "country": "United Kingdom", "metric": DEBT_METRIC,
            "value": _number(record[1]), "unit": "percent of GDP",
            "source": "ONS, Public sector finances, HF6X", "series_id": "HF6X",
        })
    if not rows:
        raise ValueError("ONS returned no monthly debt observations from 2000 onward")
    return rows


def parse_yields(html: str, country: str, series_id: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    metadata = {}
    for table in soup.find_all("table"):
        if table.get("id") == "data-table-observations":
            continue
        for row in table.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            if len(cells) == 2:
                metadata[cells[0]] = cells[1]
    if (
        metadata.get("Series ID") != series_id or metadata.get("Units") != "Percent"
        or metadata.get("Frequency") != "Monthly"
        or metadata.get("Source") != "Organization for Economic Co-operation and Development"
        or "10-Year" not in metadata.get("Title", "")
        or country not in metadata.get("Title", "")
    ):
        raise ValueError(f"Unexpected OECD/Federal Reserve yield-series metadata: {series_id}")
    table = soup.find("table", id="data-table-observations")
    if table is None:
        raise ValueError(f"Missing Federal Reserve observations table: {series_id}")
    records = [
        [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
        for row in table.find_all("tr")
    ]
    if not records or records[0] != ["DATE", "VALUE"]:
        raise ValueError(f"Unexpected Federal Reserve observations columns: {series_id}")
    rows = []
    seen = set()
    for record in records[1:]:
        if len(record) != 2 or not re.fullmatch(r"\d{4}-\d{2}-01", record[0]):
            raise ValueError(f"Malformed monthly government-bond yield: {record!r}")
        date = datetime.strptime(record[0], "%Y-%m-%d").strftime("%Y-%m-%d")
        if date in seen:
            raise ValueError(f"Duplicate monthly government-bond yield: {series_id} {date}")
        seen.add(date)
        if record[1] in {"", "."} or date < START:
            continue
        rows.append({
            "date": date, "country": country, "metric": YIELD_METRIC,
            "value": _number(record[1]), "unit": "percent per annum",
            "source": "OECD Main Economic Indicators, via Federal Reserve Bank of St. Louis",
            "series_id": series_id,
        })
    if not rows:
        raise ValueError(f"No government-bond yields from 2000 onward: {series_id}")
    return rows


def validate(frame: pd.DataFrame, previous: pd.DataFrame | None = None) -> pd.DataFrame:
    if not set(FIELDS).issubset(frame.columns) or frame[FIELDS].isna().any().any():
        raise ValueError("Debt and borrowing-cost data has missing fields")
    frame = frame[FIELDS].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame["value"] = pd.to_numeric(frame["value"], errors="raise")
    if (
        not frame["value"].map(math.isfinite).all()
        or frame.duplicated(["metric", "country", "date"]).any()
        or frame["date"].dt.day.ne(1).any()
    ):
        raise ValueError("Invalid values, duplicate months or non-monthly debt/yield data")
    expected = {(DEBT_METRIC, "United Kingdom"): ("HF6X", "percent of GDP")}
    expected.update({
        (YIELD_METRIC, country): (code, "percent per annum")
        for country, code in YIELD_SERIES.items()
    })
    groups = frame.groupby(["metric", "country"])
    if set(groups.groups) != set(expected):
        raise ValueError("Debt analysis is missing required series or contains unexpected series")
    baseline = pd.date_range(START, "2025-12-01", freq="MS")
    for key, sub in groups:
        code, unit = expected[key]
        if not sub["series_id"].eq(code).all() or not sub["unit"].eq(unit).all():
            raise ValueError(f"Incompatible debt/yield series or units: {key}")
        if missing := baseline.difference(pd.DatetimeIndex(sub["date"])).tolist():
            raise ValueError(f"Debt/yield source lost historical coverage: {key} {missing[:5]}")
    if previous is not None:
        old = previous[["metric", "country", "date"]].copy()
        old["date"] = pd.to_datetime(old["date"], errors="raise")
        current_keys = pd.MultiIndex.from_frame(frame[["metric", "country", "date"]])
        if not pd.MultiIndex.from_frame(old).isin(current_keys).all():
            raise ValueError("Debt/yield refresh lost previously published observations")
    return frame.sort_values(["metric", "country", "date"]).reset_index(drop=True)


def fetch() -> pd.DataFrame:
    debt = get_text(ONS_CSV, params={
        "format": "csv",
        "uri": "/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/hf6x/pusf",
    }, timeout=90)
    rows = parse_debt(debt)
    for country, series_id in YIELD_SERIES.items():
        rows.extend(parse_yields(
            get_text(
                f"https://fred.stlouisfed.org/data/{series_id}", timeout=90,
                headers={"Accept": "text/html", "User-Agent": requests.utils.default_user_agent()},
            ),
            country, series_id,
        ))
    return validate(pd.DataFrame(rows))
