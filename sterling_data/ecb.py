"""Fetch ECB reference rates and derive foreign-currency units per pound.

The ECB publishes monthly average units of USD, GBP, JPY and CHF per euro.
Cross-rates for one pound are therefore:

* USD per GBP = USD per EUR / GBP per EUR
* EUR per GBP = 1 / GBP per EUR
* JPY per GBP = JPY per EUR / GBP per EUR
* CHF per GBP = CHF per EUR / GBP per EUR
"""

from __future__ import annotations

import io
from urllib.parse import urlsplit

import pandas as pd
import requests

ECB_HOST = "data-api.ecb.europa.eu"
ECB_URL = (
    "https://data-api.ecb.europa.eu/service/data/"
    "EXR/M.USD+JPY+CHF+GBP.EUR.SP00.A"
    "?startPeriod=2000-01&format=csvdata"
)
SOURCE = (
    "European Central Bank, euro foreign exchange reference rates, monthly averages"
)
REQUIRED_CURRENCIES = {"USD", "GBP", "JPY", "CHF"}
OUTPUT_COLUMNS = [
    "year",
    "currency",
    "value",
    "unit",
    "months",
    "period_status",
    "source",
]


def _ensure_host(url: str) -> None:
    if (urlsplit(url).hostname or "").lower() != ECB_HOST:
        raise ValueError(f"refusing to fetch untrusted host: {url!r}")


def download_csv(url: str = ECB_URL, timeout: int = 120) -> bytes:
    """Download the official ECB monthly exchange-rate CSV."""
    _ensure_host(url)
    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "Accept": "text/csv",
            "User-Agent": "uk_decline/0.1 (sterling exchange-rate research)",
        },
    )
    response.raise_for_status()
    return response.content


def parse_monthly(payload: bytes | str | io.BytesIO) -> pd.DataFrame:
    """Parse and validate the ECB CSV into month/currency/value rows."""
    if isinstance(payload, bytes):
        payload = io.BytesIO(payload)
    frame = pd.read_csv(payload)
    required = {"TIME_PERIOD", "CURRENCY", "OBS_VALUE"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"ECB CSV missing columns: {sorted(missing)}")
    frame = frame[["TIME_PERIOD", "CURRENCY", "OBS_VALUE"]].copy()
    frame = frame[frame["CURRENCY"].isin(REQUIRED_CURRENCIES)]
    frame["date"] = pd.to_datetime(frame["TIME_PERIOD"], format="%Y-%m")
    frame["value"] = pd.to_numeric(frame["OBS_VALUE"], errors="coerce")
    if frame["value"].isna().any() or (frame["value"] <= 0).any():
        raise ValueError("ECB exchange rates must be positive numeric values")
    if set(frame["CURRENCY"]) != REQUIRED_CURRENCIES:
        raise ValueError("ECB response does not contain every required currency")
    if frame.duplicated(["date", "CURRENCY"]).any():
        raise ValueError("ECB response contains duplicate month/currency observations")
    return frame[["date", "CURRENCY", "value"]].sort_values(
        ["date", "CURRENCY"]
    ).reset_index(drop=True)


def build_annual(monthly: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return annual average foreign-currency units bought by one pound."""
    monthly = parse_monthly(download_csv()) if monthly is None else monthly.copy()
    wide = monthly.pivot(index="date", columns="CURRENCY", values="value").sort_index()
    if not REQUIRED_CURRENCIES.issubset(wide.columns):
        raise ValueError("ECB monthly series do not share complete monthly coverage")
    if wide[sorted(REQUIRED_CURRENCIES)].isna().any().any():
        raise ValueError("ECB monthly series do not share complete monthly coverage")

    cross = pd.DataFrame(index=wide.index)
    cross["USD"] = wide["USD"] / wide["GBP"]
    cross["EUR"] = 1.0 / wide["GBP"]
    cross["JPY"] = wide["JPY"] / wide["GBP"]
    cross["CHF"] = wide["CHF"] / wide["GBP"]
    cross["year"] = cross.index.year

    annual_values = cross.groupby("year")[["USD", "EUR", "JPY", "CHF"]].mean()
    month_counts = cross.groupby("year").size()
    latest_year = int(annual_values.index.max())

    units = {
        "USD": "US dollars per pound",
        "EUR": "euros per pound",
        "JPY": "Japanese yen per pound",
        "CHF": "Swiss francs per pound",
    }
    rows: list[dict] = []
    for year, values in annual_values.iterrows():
        months = int(month_counts.loc[year])
        status = "year_to_date" if int(year) == latest_year and months < 12 else "full_year"
        for currency in ("USD", "EUR", "JPY", "CHF"):
            rows.append(
                {
                    "year": int(year),
                    "currency": currency,
                    "value": float(values[currency]),
                    "unit": units[currency],
                    "months": months,
                    "period_status": status,
                    "source": SOURCE,
                }
            )
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
