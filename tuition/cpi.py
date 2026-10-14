"""Saved BLS CPI-U annual averages shared by all tuition comparisons.

Refresh explicitly with ``python -m tuition.cpi``. Calculations read the saved
series, so historical and PPP charts use identical inputs without network access.
"""

from __future__ import annotations

import csv
import datetime as dt
import math

from tuition import config
from tuition.http import get_json

SERIES_ID = "CUUR0000SA0"
SOURCE_URL = f"https://api.bls.gov/publicAPI/v2/timeseries/data/{SERIES_ID}"
START_YEAR = 1963


def parse(payload: dict, start: int, end: int) -> dict[int, float]:
    """Select published annual (M13) observations, never monthly estimates."""
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(f"BLS CPI request failed: {payload.get('message')}")
    series = payload.get("Results", {}).get("series", [])
    if len(series) != 1 or series[0].get("seriesID") != SERIES_ID:
        raise ValueError("BLS CPI response contains an unexpected series")
    annual = {}
    for row in series[0].get("data", []):
        if row.get("period") != "M13":
            continue
        year, value = int(row["year"]), float(row["value"])
        if not start <= year <= end or year in annual:
            raise ValueError(f"BLS CPI duplicate or unexpected annual year: {year}")
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"BLS CPI invalid annual index for {year}: {value}")
        annual[year] = value
    if set(annual) != set(range(start, end + 1)):
        raise ValueError(f"BLS CPI missing annual observations for {start}-{end}")
    return annual


def load_cpi(start: int, end: int) -> dict[int, float]:
    """Read exact-year observations; unpublished years remain absent."""
    annual = {}
    with open(config.CPI_CSV, newline="") as fh:
        for row in csv.DictReader(fh):
            year, value = int(row["year"]), float(row["index"])
            if row["series_id"] != SERIES_ID or year in annual:
                raise ValueError(f"Invalid saved BLS CPI series/year: {year}")
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"Invalid saved BLS CPI index for {year}")
            if year >= dt.date.today().year:
                raise ValueError(f"Incomplete calendar year in saved BLS CPI: {year}")
            annual[year] = value
    if config.REAL_BASE_YEAR not in annual:
        raise ValueError("Saved BLS CPI is missing the deflation base year")
    return {year: value for year, value in annual.items() if start <= year <= end}


def main() -> None:
    end = dt.date.today().year - 1
    annual = {}
    # Unregistered BLS requests support at most ten years per request.
    for start in range(START_YEAR, end + 1, 10):
        stop = min(start + 9, end)
        payload = get_json(SOURCE_URL, {
            "startyear": start, "endyear": stop, "annualaverage": "true",
        })
        annual.update(parse(payload, start, stop))
    with open(config.CPI_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["year", "index", "series_id", "source_url", "notes"],
            lineterminator="\n",
        )
        writer.writeheader()
        for year, value in sorted(annual.items()):
            writer.writerow({
                "year": year, "index": value, "series_id": SERIES_ID,
                "source_url": SOURCE_URL,
                "notes": (
                    "BLS published annual average (M13) of 11 months; "
                    "October unavailable due to the 2025 lapse in appropriations"
                    if year == 2025 else "BLS published annual average (M13); 1982-84=100"
                ),
            })
    print(f"[CPI] wrote {len(annual)} annual observations through {end}: {config.CPI_CSV}")


if __name__ == "__main__":
    main()
