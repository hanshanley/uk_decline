"""The four UK nations and their NHS-statistics source portals.

Health is devolved, so each nation publishes waiting-time statistics separately
and on its own definitions/cadence. This module is the single source of truth for
nation names, short codes, and source metadata.
"""

from __future__ import annotations

from typing import NamedTuple


class Nation(NamedTuple):
    name: str
    code: str  # short code used in tidy rows / charts (ENG, SCO, WAL, NIR)
    source_name: str
    portal: str


NATIONS: list[Nation] = [
    Nation(
        "England",
        "ENG",
        "NHS England",
        "https://www.england.nhs.uk/statistics/statistical-work-areas/",
    ),
    Nation(
        "Scotland",
        "SCO",
        "Public Health Scotland",
        "https://www.opendata.nhs.scot/",
    ),
    Nation(
        "Wales",
        "WAL",
        "StatsWales (Welsh Government)",
        "https://statswales.gov.wales/",
    ),
    Nation(
        "Northern Ireland",
        "NIR",
        "Department of Health (NI)",
        "https://www.health-ni.gov.uk/topics/doh-statistics-and-research/hospital-waiting-times-statistics",
    ),
]

BY_CODE: dict[str, Nation] = {n.code: n for n in NATIONS}
BY_NAME: dict[str, Nation] = {n.name: n for n in NATIONS}


def codes() -> list[str]:
    return [n.code for n in NATIONS]


def name_for_code(code: str) -> str:
    n = BY_CODE.get(code)
    return n.name if n else code
