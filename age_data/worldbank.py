"""World Bank WDI client: broad age-structure shares and dependency ratios.

Endpoint: ``https://api.worldbank.org/v2/country/{codes}/indicator/{indicator}`` (no API
key). Underlying data is the UN Population Division's World Population Prospects,
redistributed by the World Bank (see :data:`age_data.config.CITATIONS`).
"""

from __future__ import annotations

from typing import Iterable, Iterator

from europe_data._worldbank import observations

from . import config
from ._http import get_json
from .combine import make_row

SOURCE = config.SOURCE_WB
# Metric ids this source owns (used to scope the offline fallback).
METRICS = tuple(config.BROAD_INDICATORS)
COUNTRY_BATCH_SIZE = 10


def _batches(items: list[str], size: int = COUNTRY_BATCH_SIZE) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _fetch_indicator(
    metric: str, indicator: str, iso3s: list[str], start: int, end: int
) -> Iterator[dict]:
    for row in observations(indicator, iso3s, start, end, download=get_json):
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


def fetch(start: int, end: int, iso3s: Iterable[str] | None = None) -> list[dict]:
    """Fetch broad age-structure + dependency-ratio rows for the given years/countries."""
    codes = list(iso3s) if iso3s is not None else config.iso3_codes()
    batch_size = len(codes) if start == end else COUNTRY_BATCH_SIZE
    out: list[dict] = []
    for metric, (indicator, _unit) in config.BROAD_INDICATORS.items():
        for batch in _batches(codes, batch_size):
            out.extend(_fetch_indicator(metric, indicator, batch, start, end))
    return out
