"""World Bank PIP (Poverty and Inequality Platform) client: median income.

Endpoint: https://api.worldbank.org/pip/v1/pip
Returns the median daily household per-capita income/consumption in 2021 PPP $.

PPPs adjust for price differences, but survey welfare definitions can still differ.
The UK series extends beyond Eurostat's coverage, which ends around 2018. Values are
per person per day; multiply by 365 for an annual figure (documented in the README).
"""

from __future__ import annotations

import math
from typing import Iterable

from . import countries
from ._http import get_json

BASE = "https://api.worldbank.org/pip/v1/pip"
AUX_COUNTRIES = "https://api.worldbank.org/pip/v1/aux?table=countries&format=json"
SOURCE = "World Bank PIP"
PPP_VERSION = 2021
UNIT = f"{PPP_VERSION} PPP $ per day"
METRIC = "median_income_pip"

# When a country reports both, prefer income over consumption for European comparisons.
_WELFARE_PREF = {"income": 0, "consumption": 1}

_valid_codes: set[str] | None = None


def valid_country_codes() -> set[str]:
    """ISO3 codes that actually exist in PIP (querying others yields a 404)."""
    global _valid_codes
    if _valid_codes is None:
        payload = get_json(AUX_COUNTRIES)
        rows = payload if isinstance(payload, list) else []
        _valid_codes = {r["country_code"] for r in rows if r.get("country_code")}
    return _valid_codes


def fetch(
    start: int,
    end: int,
    iso3s: Iterable[str] | None = None,
) -> list[dict]:
    """Fetch PIP median-income rows (national level) for the given years/countries.

    Returns tidy rows with the source's comparability identifier and welfare type.
    """
    requested = list(iso3s) if iso3s is not None else [*countries.iso3_codes(), "USA"]
    # PIP returns a 404 if *any* requested code is absent, so pre-filter to valid codes.
    valid = valid_country_codes()
    iso3_list = [c for c in requested if c in valid]
    if not iso3_list:
        return []
    payload = get_json(
        BASE,
        params={
            "country": ",".join(iso3_list),
            "year": "all",
            "fill_gaps": "false",
            "format": "json",
            "ppp_version": PPP_VERSION,
        },
    )
    if not isinstance(payload, list):
        return []

    # Choose one observation per (country, year): national level, preferred welfare type.
    # Each entry is (preference_rank, record); lower rank wins on ties (first-seen).
    best: dict[tuple[str, int], tuple[int, dict]] = {}
    for row in payload:
        if row.get("reporting_level") not in (None, "national"):
            continue
        if row.get("is_interpolated") is True:
            continue
        median = row.get("median")
        year = row.get("reporting_year")
        iso3 = row.get("country_code")
        if median is None or year is None or iso3 is None:
            continue
        year = int(year)
        if not (start <= year <= end):
            continue
        if iso3 not in iso3_list or row.get("welfare_type") not in _WELFARE_PREF:
            raise ValueError(f"Unexpected PIP survey country or welfare definition: {row}")
        value = float(median)
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid PIP median: {iso3} {year}")
        key = (iso3, year)
        pref = _WELFARE_PREF[row["welfare_type"]]
        prev = best.get(key)
        if prev is None or pref < prev[0]:
            curated = countries.BY_ISO3.get(iso3)
            name = curated.name if curated else (row.get("country_name") or iso3)
            best[key] = (pref, {
                "iso3": iso3,
                "country": name,
                "year": year,
                "metric": METRIC,
                "value": value,
                "unit": UNIT,
                "source": SOURCE,
                "survey_comparability": row.get("survey_comparability"),
                "welfare_type": row.get("welfare_type"),
            })

    return [record for _, record in best.values()]
