"""World Bank WDI client: broad age-structure shares and dependency ratios.

Endpoint: ``https://api.worldbank.org/v2/country/{codes}/indicator/{indicator}`` (no API
key). Underlying data is the UN Population Division's World Population Prospects,
redistributed by the World Bank (see :data:`age_data.config.CITATIONS`).
"""

from __future__ import annotations

from typing import Iterable, Iterator

from . import config
from ._http import get_json
from .combine import make_row

SOURCE = config.SOURCE_WB
# Metric ids this source owns (used to scope the offline fallback).
METRICS = tuple(config.BROAD_INDICATORS)


def _fetch_indicator(
    metric: str, indicator: str, iso3s: list[str], start: int, end: int
) -> Iterator[dict]:
    codes = ";".join(iso3s)
    page = 1
    while True:
        payload = get_json(
            f"{config.WORLD_BANK_BASE}/country/{codes}/indicator/{indicator}",
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
            iso3 = row.get("countryiso3code") or ""
            if value is None or iso3 not in config.BY_ISO3:
                continue
            yield make_row(
                iso3=iso3,
                year=int(row["date"]),
                metric=metric,
                value=float(value),
                source=SOURCE,
            )
        if page >= int(meta.get("pages", 1)):
            return
        page += 1


def fetch(start: int, end: int, iso3s: Iterable[str] | None = None) -> list[dict]:
    """Fetch broad age-structure + dependency-ratio rows for the given years/countries."""
    codes = list(iso3s) if iso3s is not None else config.iso3_codes()
    out: list[dict] = []
    for metric, (indicator, _unit) in config.BROAD_INDICATORS.items():
        out.extend(_fetch_indicator(metric, indicator, codes, start, end))
    return out
