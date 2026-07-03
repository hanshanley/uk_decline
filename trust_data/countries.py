"""Country list for the trust pipeline: the UK (primary) plus EU-27 + US comparators.

Every country carries the codes needed by both data sources:
  * ``iso3`` -> World Bank WGI country code *and* OECD SDMX ``REF_AREA`` (e.g. ``GBR``)
  * ``iso2`` -> ISO 3166-1 alpha-2 (e.g. ``GB``)
  * ``group`` -> analytical bucket used for the UK-vs-comparators framing (UK / EU / US)

The UK is listed first and flagged via :data:`UK_ISO3`; charts and the summary highlight it
against the EU-27 and US comparators.
"""

from __future__ import annotations

from typing import NamedTuple

# Analytical groups.
UK = "UK"
EU = "EU"
US = "US"

UK_ISO3 = "GBR"


class Country(NamedTuple):
    name: str
    iso3: str   # World Bank WGI + OECD REF_AREA
    iso2: str
    group: str  # UK / EU / US


# UK first (primary), then the EU-27 member states, then the US comparator.
COUNTRIES: list[Country] = [
    Country("United Kingdom", "GBR", "GB", UK),
    Country("Austria", "AUT", "AT", EU),
    Country("Belgium", "BEL", "BE", EU),
    Country("Bulgaria", "BGR", "BG", EU),
    Country("Croatia", "HRV", "HR", EU),
    Country("Cyprus", "CYP", "CY", EU),
    Country("Czechia", "CZE", "CZ", EU),
    Country("Denmark", "DNK", "DK", EU),
    Country("Estonia", "EST", "EE", EU),
    Country("Finland", "FIN", "FI", EU),
    Country("France", "FRA", "FR", EU),
    Country("Germany", "DEU", "DE", EU),
    Country("Greece", "GRC", "GR", EU),
    Country("Hungary", "HUN", "HU", EU),
    Country("Ireland", "IRL", "IE", EU),
    Country("Italy", "ITA", "IT", EU),
    Country("Latvia", "LVA", "LV", EU),
    Country("Lithuania", "LTU", "LT", EU),
    Country("Luxembourg", "LUX", "LU", EU),
    Country("Malta", "MLT", "MT", EU),
    Country("Netherlands", "NLD", "NL", EU),
    Country("Poland", "POL", "PL", EU),
    Country("Portugal", "PRT", "PT", EU),
    Country("Romania", "ROU", "RO", EU),
    Country("Slovakia", "SVK", "SK", EU),
    Country("Slovenia", "SVN", "SI", EU),
    Country("Spain", "ESP", "ES", EU),
    Country("Sweden", "SWE", "SE", EU),
    Country("United States", "USA", "US", US),
]

BY_ISO3: dict[str, Country] = {c.iso3: c for c in COUNTRIES}


def iso3_codes() -> list[str]:
    """World Bank / OECD country codes for every country in the set."""
    return [c.iso3 for c in COUNTRIES]


def name_for_iso3(iso3: str) -> str:
    c = BY_ISO3.get(iso3)
    return c.name if c else iso3


def group_for_iso3(iso3: str) -> str:
    """Analytical bucket (UK / EU / US) for an ISO3 code; falls back to the code."""
    c = BY_ISO3.get(iso3)
    return c.group if c else iso3
