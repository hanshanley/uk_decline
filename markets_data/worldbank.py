"""World Bank WDI client: stock-market size indicators for selected regions.

Endpoint: https://api.worldbank.org/v2/country/{codes}/indicator/{indicator}
No API key required. Region codes are joined with ``;``; the API pages results.
"""

from __future__ import annotations

from typing import Iterable, Iterator

from europe_data._http import get_json
from europe_data._worldbank import observations

from . import markets, regions

BASE = "https://api.worldbank.org/v2"


def _fetch_indicator(
    indicator: str, codes: list[str], start: int, end: int
) -> Iterator[dict]:
    metric_id = markets.BY_INDICATOR[indicator]
    for row in observations(indicator, codes, start, end, download=get_json):
        value = row.get("value")
        if value is None:
            continue
        country = row.get("country") or {}
        code = row.get("countryiso3code") or country.get("id") or ""
        name = regions.name_for_code(code) if code else (country.get("value") or code)
        yield markets.make_row(name, code, int(row["date"]), metric_id, float(value))


def fetch(
    start: int,
    end: int,
    codes: Iterable[str] | None = None,
    indicators: Iterable[str] | None = None,
) -> list[dict]:
    """Fetch WDI stock-market-size rows for the given years and regions.

    Returns tidy dict rows: region, region_code, year, metric, value, unit, source.
    """
    code_list = list(codes) if codes is not None else regions.codes()
    ind_list = (
        list(indicators)
        if indicators is not None
        else [m.wb_indicator for m in markets.METRICS.values() if m.wb_indicator]
    )
    out: list[dict] = []
    for indicator in ind_list:
        out.extend(_fetch_indicator(indicator, code_list, start, end))
    return out


def fetch_us_cpi(start: int, end: int) -> dict[int, float]:
    """Fetch US CPI (World Bank ``FP.CPI.TOTL``, 2010=100) as ``{year: index}``.

    Used to deflate the nominal current-US$ market-cap series to real terms. Only
    non-null observations are returned; the caller decides the rebasing year.
    """
    cpi: dict[int, float] = {}
    for row in observations(markets.CPI_INDICATOR, ["USA"], start, end, download=get_json):
        if row.get("value") is not None:
            cpi[int(row["date"])] = float(row["value"])
    return cpi
