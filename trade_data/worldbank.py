"""Fetch World Bank trade-openness data for the UK and major peers."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlsplit

import requests

BASE = "https://api.worldbank.org/v2"
INDICATOR = "NE.TRD.GNFS.ZS"
SOURCE = (
    "World Bank, World Development Indicators, Trade (% of GDP), "
    "indicator NE.TRD.GNFS.ZS"
)
COUNTRIES = {
    "GBR": "United Kingdom",
    "DEU": "Germany",
    "FRA": "France",
    "JPN": "Japan",
    "USA": "United States",
}
ROW_FIELDS = ["country", "country_code", "year", "value", "unit", "source"]


def _ensure_host(url: str) -> None:
    if (urlsplit(url).hostname or "").lower() != "api.worldbank.org":
        raise ValueError(f"refusing to fetch untrusted host: {url!r}")


def parse_payload(payload) -> tuple[int, list[dict]]:
    """Parse one World Bank page and return ``(pages, tidy_rows)``."""
    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        raise ValueError("unexpected World Bank response")
    meta, observations = payload[0], payload[1]
    rows: list[dict] = []
    for observation in observations:
        value = observation.get("value")
        code = observation.get("countryiso3code")
        if value is None or code not in COUNTRIES:
            continue
        rows.append(
            {
                "country": COUNTRIES[code],
                "country_code": code,
                "year": int(observation["date"]),
                "value": float(value),
                "unit": "percent of GDP",
                "source": SOURCE,
            }
        )
    return int(meta.get("pages", 1)), rows


def fetch(start: int = 2000, end: int | None = None, timeout: int = 60) -> list[dict]:
    """Fetch annual trade as a percentage of GDP."""
    end = end or date.today().year
    codes = ";".join(COUNTRIES)
    url = f"{BASE}/country/{codes}/indicator/{INDICATOR}"
    _ensure_host(url)
    page = 1
    rows: list[dict] = []
    while True:
        response = requests.get(
            url,
            params={
                "format": "json",
                "date": f"{start}:{end}",
                "per_page": 1000,
                "page": page,
            },
            timeout=timeout,
            headers={"User-Agent": "uk_decline/0.1 (trade openness research)"},
        )
        response.raise_for_status()
        pages, parsed = parse_payload(response.json())
        rows.extend(parsed)
        if page >= pages:
            break
        page += 1
    rows.sort(key=lambda row: (row["country_code"], row["year"]))
    return rows

