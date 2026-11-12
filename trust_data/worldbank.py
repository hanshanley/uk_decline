"""World Bank client for the Worldwide Governance Indicators (WGI).

Endpoint: https://api.worldbank.org/v2/country/{codes}/indicator/{indicator}?source=3
No API key required. WGI lives in database ``source=3``; the ``estimate`` series
(``GOV_WGI_*.EST``, approx. -2.5..+2.5) are used as governance-quality proxies for trust.
Country codes are joined with ``;`` and the API pages results.
"""

from __future__ import annotations

from typing import Iterable, Iterator

from europe_data._http import get_json
from europe_data._worldbank import observations

from . import countries, metrics

BASE = "https://api.worldbank.org/v2"
WGI_SOURCE = 3

# World Bank WGI estimate indicator id -> canonical trust metric id.
INDICATORS: dict[str, str] = {
    "GOV_WGI_VA.EST": "wgi_voice_accountability",
    "GOV_WGI_GE.EST": "wgi_government_effectiveness",
    "GOV_WGI_RL.EST": "wgi_rule_of_law",
    "GOV_WGI_CC.EST": "wgi_control_of_corruption",
}

SOURCE = "World Bank WGI"


def _fetch_indicator(
    indicator: str, iso3s: list[str], start: int, end: int
) -> Iterator[dict]:
    metric = INDICATORS[indicator]
    for row in observations(
        indicator, iso3s, start, end, source=WGI_SOURCE, download=get_json,
    ):
        value = row.get("value")
        if value is None:
            continue
        iso3 = row.get("countryiso3code") or ""
        if iso3 not in countries.BY_ISO3:
            continue
        yield metrics.make_row(
            iso3=iso3,
            country=countries.name_for_iso3(iso3),
            year=int(row["date"]),
            metric=metric,
            value=float(value),
            source=SOURCE,
        )


def fetch(
    start: int,
    end: int,
    iso3s: Iterable[str] | None = None,
    indicators: Iterable[str] | None = None,
) -> list[dict]:
    """Fetch WGI governance-estimate rows for the given years and countries.

    Returns tidy dict rows (see :data:`trust_data.metrics.ROW_FIELDS`).
    """
    iso3_list = list(iso3s) if iso3s is not None else countries.iso3_codes()
    ind_list = list(indicators) if indicators is not None else list(INDICATORS)
    out: list[dict] = []
    for indicator in ind_list:
        out.extend(_fetch_indicator(indicator, iso3_list, start, end))
    return out
