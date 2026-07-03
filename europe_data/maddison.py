"""Maddison Project Database client: long-run REAL GDP per capita (PPP).

Source: Bolt & van Zanden, Maddison Project Database 2023, served as a clean CSV by
Our World in Data. Values are **real** GDP per capita — expressed in international $ at
**2011 prices** (i.e. adjusted for inflation *and* for cross-country price levels/PPP).

This is what lets the GDP-per-capita comparison reach the **1970s**: the World Bank PPP
series only starts in 1990, whereas Maddison provides continuous annual coverage back to
1970 (and earlier) for the UK, US, and European peers.

CSV columns: ``entity, code, year, gdp_per_capita`` (plus an annotations column).
"""

from __future__ import annotations

import csv
import io
from typing import Iterable

from . import countries
from ._http import get_text

# Full, unfiltered CSV of the OWID "GDP per capita (Maddison)" indicator.
URL = (
    "https://ourworldindata.org/grapher/gdp-per-capita-maddison.csv"
    "?csvType=full&useColumnShortNames=true"
)

METRIC = "gdp_per_capita_real_maddison"
UNIT = "real, constant 2011 international $ (PPP)"
SOURCE = "Maddison Project Database 2023 (via Our World in Data)"


def fetch(
    start: int,
    end: int,
    iso3s: Iterable[str] | None = None,
) -> list[dict]:
    """Fetch Maddison real GDP-per-capita rows for the given years and countries.

    Returns tidy dict rows: iso3, country, year, metric, value, unit, source.
    Only real observations from the source CSV are emitted (no gap-filling/interpolation).
    """
    wanted = set(iso3s) if iso3s is not None else set(countries.gdp_iso3_codes(include_aggregates=False))
    text = get_text(URL)
    reader = csv.DictReader(io.StringIO(text))

    out: list[dict] = []
    for row in reader:
        iso3 = row.get("code")
        raw = row.get("gdp_per_capita")
        year_s = row.get("year")
        if not iso3 or iso3 not in wanted or not raw or not year_s:
            continue
        year = int(year_s)
        if not (start <= year <= end):
            continue
        out.append(
            {
                "iso3": iso3,
                "country": countries.name_for_iso3(iso3),
                "year": year,
                "metric": METRIC,
                "value": float(raw),
                "unit": UNIT,
                "source": SOURCE,
            }
        )
    return out
