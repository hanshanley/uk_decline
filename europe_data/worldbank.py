"""World Bank WDI client: GDP per capita, PPP (nominal + constant international $).

Endpoint: https://api.worldbank.org/v2/country/{codes}/indicator/{indicator}
No API key required. Country codes are joined with ``;``; the API pages results.
"""

from __future__ import annotations

from typing import Iterable, Iterator

from . import countries
from ._http import get_json

BASE = "https://api.worldbank.org/v2"

# indicator id -> (metric name, unit label)
INDICATORS: dict[str, tuple[str, str]] = {
    "NY.GDP.PCAP.PP.CD": ("gdp_per_capita_ppp_current", "current international $"),
    "NY.GDP.PCAP.PP.KD": ("gdp_per_capita_ppp_constant", "constant 2021 international $"),
}

SOURCE = "World Bank WDI"


def _fetch_indicator(
    indicator: str, iso3s: list[str], start: int, end: int
) -> Iterator[dict]:
    metric, unit = INDICATORS[indicator]
    codes = ";".join(iso3s)
    page = 1
    while True:
        payload = get_json(
            f"{BASE}/country/{codes}/indicator/{indicator}",
            params={
                "format": "json",
                "per_page": 1000,
                "date": f"{start}:{end}",
                "page": page,
            },
        )
        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            return
        meta, rows = payload[0], payload[1]
        for row in rows:
            value = row.get("value")
            if value is None:
                continue
            iso3 = row.get("countryiso3code") or ""
            curated = countries.BY_ISO3.get(iso3)
            name = curated.name if curated else (row.get("country") or {}).get("value") or iso3
            yield {
                "iso3": iso3,
                "country": name,
                "year": int(row["date"]),
                "metric": metric,
                "value": float(value),
                "unit": unit,
                "source": SOURCE,
            }
        if page >= int(meta.get("pages", 1)):
            return
        page += 1


def fetch(
    start: int,
    end: int,
    iso3s: Iterable[str] | None = None,
    indicators: Iterable[str] | None = None,
) -> list[dict]:
    """Fetch WDI GDP-per-capita PPP rows for the given years and countries.

    Returns tidy dict rows: iso3, country, year, metric, value, unit, source.
    """
    iso3_list = list(iso3s) if iso3s is not None else countries.iso3_codes(include_aggregates=True)
    ind_list = list(indicators) if indicators is not None else list(INDICATORS)
    out: list[dict] = []
    for indicator in ind_list:
        out.extend(_fetch_indicator(indicator, iso3_list, start, end))
    return out
