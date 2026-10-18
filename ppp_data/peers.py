"""The countries plotted in the PPP figures, and their house-style colours.

Country codes and names come from :mod:`europe_data.countries` — the single curated
source in this repository — so nothing is duplicated here. This module only decides
*which* of those countries appear on the PPP charts and in what colour.
"""

from __future__ import annotations

from typing import NamedTuple

from europe_data import countries
from vizstyle import country_color


class Peer(NamedTuple):
    iso3: str
    label: str        # the label drawn on the chart (may be shorter than the full name)
    colour: str
    linestyle: str
    linewidth: float


UK = "GBR"
US = "USA"
POLAND = Peer("POL", "Poland", country_color("POL"), "--", 2.1)
EU_AVERAGE = Peer("EUU", "EU average", country_color("EUU"), "--", 2.0)

# The UK is always terracotta and heavier than everything else; the US is near-black as
# the primary comparator. These countries have World Bank PPP series back to 1990.
PEERS: list[Peer] = [
    Peer("GBR", "United Kingdom", country_color("GBR"), "-", 2.8),
    Peer("USA", "United States", country_color("USA"), "-", 1.9),
    Peer("DEU", "Germany", country_color("DEU"), "-", 1.9),
    Peer("FRA", "France", country_color("FRA"), "-", 1.9),
    Peer("ITA", "Italy", country_color("ITA"), "-", 1.9),
    POLAND,
]
GDP_PEERS = [*PEERS, EU_AVERAGE]

# Peers used on the "relative to the UK" chart. The UK itself is the 100% baseline there,
# so it is not in this list; Poland is added because its convergence is the headline.
RELATIVE_PEERS: list[Peer] = [
    Peer("USA", "United States", country_color("USA"), "-", 2.8),
    Peer("DEU", "Germany", country_color("DEU"), "-", 2.0),
    Peer("FRA", "France", country_color("FRA"), "-", 2.0),
    EU_AVERAGE,
    POLAND,
]

# Peers on the price-level-index chart. The US is the numeraire (a flat 1.00 reference),
# so it is drawn as a horizontal guide rather than a series.
PRICE_LEVEL_PEERS: list[Peer] = [
    Peer("GBR", "United Kingdom", country_color("GBR"), "-", 2.8),
    Peer("DEU", "Germany", country_color("DEU"), "-", 1.9),
    Peer("FRA", "France", country_color("FRA"), "-", 1.9),
    Peer("ITA", "Italy", country_color("ITA"), "-", 1.9),
    POLAND,
]

# Every ISO3 the fetchers need, de-duplicated and stably ordered.
ALL_ISO3: list[str] = list(
    dict.fromkeys(
        p.iso3 for group in (PEERS, RELATIVE_PEERS, PRICE_LEVEL_PEERS) for p in group
    )
)

# World Bank aggregate codes (e.g. the EU) are not countries: they have no single currency
# and therefore no meaningful exchange rate or price level index.
AGGREGATE_ISO3: frozenset[str] = frozenset(a.iso3 for a in countries.WB_AGGREGATES)

# Countries only (aggregates excluded) — the valid domain for FX/PPP-factor lookups.
COUNTRY_ISO3: list[str] = [c for c in ALL_ISO3 if c not in AGGREGATE_ISO3]


def name_for(iso3: str) -> str:
    """Full country name for an ISO3 code, via the curated europe_data table."""
    return countries.name_for_iso3(iso3)
