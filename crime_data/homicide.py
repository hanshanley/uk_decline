"""World Bank client for the intentional homicide rate (per 100,000 population).

Endpoint: ``https://api.worldbank.org/v2/country/{codes}/indicator/VC.IHR.PSRC.P5``.
No API key required. The underlying data are compiled by the **United Nations Office on
Drugs and Crime (UNODC)** and redistributed via the World Bank's World Development
Indicators. Homicide is the most internationally comparable crime statistic, so it lets us
put the UK against the US and EU-27 peers on a like-for-like basis.
"""

from __future__ import annotations

import datetime as _dt
from typing import Iterable, Iterator

import requests

from . import countries

BASE = "https://api.worldbank.org/v2"
INDICATOR = "VC.IHR.PSRC.P5"
METRIC = "homicide_rate_per_100k"
UNIT = "per 100,000 population"
SOURCE = "UN Office on Drugs and Crime (UNODC) via World Bank WDI"

_UA = {"User-Agent": "uk_decline/0.1 (crime statistics research)"}


def _fetch(codes: list[str], start: int, end: int, timeout: int = 60) -> Iterator[dict]:
    joined = ";".join(codes)
    page = 1
    while True:
        resp = requests.get(
            f"{BASE}/country/{joined}/indicator/{INDICATOR}",
            params={"format": "json", "per_page": 1000,
                    "date": f"{start}:{end}", "page": page},
            headers=_UA, timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            return
        meta, rows = payload[0], payload[1]
        for row in rows:
            value = row.get("value")
            if value is None:
                continue
            iso3 = row.get("countryiso3code") or ""
            if iso3 not in countries.BY_ISO3:
                continue
            yield {
                "iso3": iso3,
                "country": countries.name_for_iso3(iso3),
                "year": int(row["date"]),
                "metric": METRIC,
                "value": float(value),
                "unit": UNIT,
                "source": SOURCE,
            }
        if page >= int(meta.get("pages", 1)):
            return
        page += 1


def build_rows(
    start: int = 1990,
    end: int | None = None,
    iso3s: Iterable[str] | None = None,
) -> list[dict]:
    """Return tidy homicide-rate rows for the UK + comparators over the given years.

    ``end`` defaults to the current calendar year so newly-published WDI data is picked up
    automatically (the API simply returns nothing for years not yet released).
    """
    if end is None:
        end = _dt.date.today().year
    codes = list(iso3s) if iso3s is not None else countries.iso3_codes()
    rows = list(_fetch(codes, start, end))
    rows.sort(key=lambda r: (r["country"], r["year"]))
    return rows
