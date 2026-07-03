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
    "NY.GDP.PCAP.KD": ("gdp_per_capita_constant_usd", "real, constant 2015 US$"),
    "NY.GDP.PCAP.CD": ("gdp_per_capita_nominal_usd", "nominal, current US$"),
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
    iso3_list = list(iso3s) if iso3s is not None else countries.gdp_iso3_codes(include_aggregates=True)
    ind_list = list(indicators) if indicators is not None else list(INDICATORS)
    out: list[dict] = []
    for indicator in ind_list:
        out.extend(_fetch_indicator(indicator, iso3_list, start, end))
    return out


def us_cpi(start: int, end: int) -> dict[int, float]:
    """US CPI index (FP.CPI.TOTL) by year — used to deflate current-US$ to constant US$.

    Always fetched from 1960 so the 2015 base year is present regardless of ``start``.
    """
    out: dict[int, float] = {}
    payload = get_json(
        f"{BASE}/country/USA/indicator/FP.CPI.TOTL",
        params={"format": "json", "per_page": 1000, "date": f"{min(start, 1960)}:{end}"},
    )
    if isinstance(payload, list) and len(payload) > 1 and payload[1]:
        for row in payload[1]:
            if row.get("value") is not None:
                out[int(row["date"])] = float(row["value"])
    return out


def deflate_to_real_usd(rows: list[dict], cpi: dict[int, float], base_year: int = 2015) -> list[dict]:
    """Add a ``gdp_per_capita_real_usd`` metric: current-US$ GDP per capita expressed in
    constant ``base_year`` US$ by deflating with US CPI (market exchange rates preserved,
    inflation removed). This is the series in which the UK eclipsed the US in 2007.
    """
    base = cpi.get(base_year)
    if not base:
        return []
    real: list[dict] = []
    for r in rows:
        if r["metric"] != "gdp_per_capita_nominal_usd":
            continue
        c = cpi.get(r["year"])
        if not c:
            continue
        real.append({
            **r,
            "metric": "gdp_per_capita_real_usd",
            "value": r["value"] * base / c,
            "unit": f"real, constant {base_year} US$ (US-CPI deflated, market FX)",
            "source": "World Bank WDI (NY.GDP.PCAP.CD deflated by US CPI, FP.CPI.TOTL)",
        })
    return real
