"""Country set for the international homicide comparison: UK (primary) + EU-27 + US.

Each country carries its World Bank / ISO3 code, display name, and an analytical group
(UK / EU / US) so charts can highlight the UK against its peers. Mirrors the small,
self-contained country modules used elsewhere (e.g. ``trust_data/countries.py``).
"""

from __future__ import annotations

from typing import NamedTuple

UK = "UK"
EU = "EU"
US = "US"

UK_ISO3 = "GBR"


class Country(NamedTuple):
    name: str
    iso3: str
    group: str


COUNTRIES: list[Country] = [
    Country("United Kingdom", "GBR", UK),
    Country("Austria", "AUT", EU),
    Country("Belgium", "BEL", EU),
    Country("Bulgaria", "BGR", EU),
    Country("Croatia", "HRV", EU),
    Country("Cyprus", "CYP", EU),
    Country("Czechia", "CZE", EU),
    Country("Denmark", "DNK", EU),
    Country("Estonia", "EST", EU),
    Country("Finland", "FIN", EU),
    Country("France", "FRA", EU),
    Country("Germany", "DEU", EU),
    Country("Greece", "GRC", EU),
    Country("Hungary", "HUN", EU),
    Country("Ireland", "IRL", EU),
    Country("Italy", "ITA", EU),
    Country("Latvia", "LVA", EU),
    Country("Lithuania", "LTU", EU),
    Country("Luxembourg", "LUX", EU),
    Country("Malta", "MLT", EU),
    Country("Netherlands", "NLD", EU),
    Country("Poland", "POL", EU),
    Country("Portugal", "PRT", EU),
    Country("Romania", "ROU", EU),
    Country("Slovakia", "SVK", EU),
    Country("Slovenia", "SVN", EU),
    Country("Spain", "ESP", EU),
    Country("Sweden", "SWE", EU),
    Country("United States", "USA", US),
]

BY_ISO3: dict[str, Country] = {c.iso3: c for c in COUNTRIES}


def iso3_codes() -> list[str]:
    return [c.iso3 for c in COUNTRIES]


def name_for_iso3(iso3: str) -> str:
    c = BY_ISO3.get(iso3)
    return c.name if c else iso3


def group_for_iso3(iso3: str) -> str:
    c = BY_ISO3.get(iso3)
    return c.group if c else iso3
