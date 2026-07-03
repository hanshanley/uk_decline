"""Curated geographic-Europe country list with cross-source code mappings.

Each country carries the codes needed by every data source:
  * ``iso3``     -> World Bank WDI and PIP country code (e.g. ``GBR``)
  * ``iso2``     -> ISO 3166-1 alpha-2 (e.g. ``GB``)
  * ``eurostat`` -> Eurostat ``geo`` code (mostly ISO2, but Greece=``EL``, UK=``UK``)

The World Bank ``ECS`` region also spans Central Asia, so we rely on this explicit
allow-list rather than a region filter. Russia and Turkey are excluded by default as
transcontinental; micro-states with no survey data are kept for completeness but will
simply yield sparse rows.
"""

from __future__ import annotations

from typing import NamedTuple


class Country(NamedTuple):
    name: str
    iso3: str
    iso2: str
    eurostat: str


# name, iso3 (World Bank / PIP), iso2, eurostat geo
COUNTRIES: list[Country] = [
    Country("Albania", "ALB", "AL", "AL"),
    Country("Andorra", "AND", "AD", "AD"),
    Country("Austria", "AUT", "AT", "AT"),
    Country("Belarus", "BLR", "BY", "BY"),
    Country("Belgium", "BEL", "BE", "BE"),
    Country("Bosnia and Herzegovina", "BIH", "BA", "BA"),
    Country("Bulgaria", "BGR", "BG", "BG"),
    Country("Croatia", "HRV", "HR", "HR"),
    Country("Cyprus", "CYP", "CY", "CY"),
    Country("Czechia", "CZE", "CZ", "CZ"),
    Country("Denmark", "DNK", "DK", "DK"),
    Country("Estonia", "EST", "EE", "EE"),
    Country("Finland", "FIN", "FI", "FI"),
    Country("France", "FRA", "FR", "FR"),
    Country("Germany", "DEU", "DE", "DE"),
    Country("Greece", "GRC", "GR", "EL"),
    Country("Hungary", "HUN", "HU", "HU"),
    Country("Iceland", "ISL", "IS", "IS"),
    Country("Ireland", "IRL", "IE", "IE"),
    Country("Italy", "ITA", "IT", "IT"),
    Country("Kosovo", "XKX", "XK", "XK"),
    Country("Latvia", "LVA", "LV", "LV"),
    Country("Liechtenstein", "LIE", "LI", "LI"),
    Country("Lithuania", "LTU", "LT", "LT"),
    Country("Luxembourg", "LUX", "LU", "LU"),
    Country("Malta", "MLT", "MT", "MT"),
    Country("Moldova", "MDA", "MD", "MD"),
    Country("Monaco", "MCO", "MC", "MC"),
    Country("Montenegro", "MNE", "ME", "ME"),
    Country("Netherlands", "NLD", "NL", "NL"),
    Country("North Macedonia", "MKD", "MK", "MK"),
    Country("Norway", "NOR", "NO", "NO"),
    Country("Poland", "POL", "PL", "PL"),
    Country("Portugal", "PRT", "PT", "PT"),
    Country("Romania", "ROU", "RO", "RO"),
    Country("San Marino", "SMR", "SM", "SM"),
    Country("Serbia", "SRB", "RS", "RS"),
    Country("Slovakia", "SVK", "SK", "SK"),
    Country("Slovenia", "SVN", "SI", "SI"),
    Country("Spain", "ESP", "ES", "ES"),
    Country("Sweden", "SWE", "SE", "SE"),
    Country("Switzerland", "CHE", "CH", "CH"),
    Country("Ukraine", "UKR", "UA", "UA"),
    Country("United Kingdom", "GBR", "GB", "UK"),
]

# Non-European peers used only for GDP-per-capita comparison (NOT part of the European
# allow-list, so they never leak into Eurostat geos or the PIP country set).
NON_EUROPEAN_PEERS: list[Country] = [
    Country("United States", "USA", "US", "US"),
]

# Eurostat-only reference aggregates (no World Bank equivalent with identical membership).
EUROSTAT_AGGREGATES: list[Country] = [
    Country("European Union (27, 2020)", "EU27_2020", "EU", "EU27_2020"),
    Country("Euro area (20)", "EA20", "EA", "EA20"),
]

# World Bank reference aggregates (GDP per capita PPP is available; income is not).
WB_AGGREGATES: list[Country] = [
    Country("European Union", "EUU", "EU", "EUU"),
    Country("Euro area", "EMU", "EA", "EMU"),
]

# ---- Lookups ---------------------------------------------------------------

BY_ISO3: dict[str, Country] = {
    c.iso3: c for c in (*COUNTRIES, *NON_EUROPEAN_PEERS, *WB_AGGREGATES)
}
BY_EUROSTAT: dict[str, Country] = {
    c.eurostat: c for c in (*COUNTRIES, *EUROSTAT_AGGREGATES)
}


def iso3_codes(include_aggregates: bool = False) -> list[str]:
    """World Bank / PIP country codes for all curated European countries.

    Set ``include_aggregates`` to also include the World Bank EU/euro-area aggregates
    (valid for GDP indicators, but not for PIP, which has no aggregate rows).
    """
    codes = [c.iso3 for c in COUNTRIES]
    if include_aggregates:
        codes += [a.iso3 for a in WB_AGGREGATES]
    return codes


def gdp_iso3_codes(include_aggregates: bool = True) -> list[str]:
    """Codes for GDP-per-capita comparison: European countries + non-European peers
    (e.g. the US), optionally plus the World Bank EU/euro-area aggregates."""
    codes = [c.iso3 for c in COUNTRIES] + [c.iso3 for c in NON_EUROPEAN_PEERS]
    if include_aggregates:
        codes += [a.iso3 for a in WB_AGGREGATES]
    return codes


def eurostat_geos(include_aggregates: bool = True) -> list[str]:
    """Eurostat ``geo`` codes for all curated countries (+ optional aggregates)."""
    geos = [c.eurostat for c in COUNTRIES]
    if include_aggregates:
        geos += [a.eurostat for a in EUROSTAT_AGGREGATES]
    return geos


def name_for_iso3(iso3: str) -> str:
    c = BY_ISO3.get(iso3)
    return c.name if c else iso3


def name_for_eurostat(geo: str) -> str:
    c = BY_EUROSTAT.get(geo)
    return c.name if c else geo


def iso3_for_eurostat(geo: str) -> str:
    """Map a Eurostat geo back to ISO3 (aggregates map to their own code)."""
    c = BY_EUROSTAT.get(geo)
    return c.iso3 if c else geo
