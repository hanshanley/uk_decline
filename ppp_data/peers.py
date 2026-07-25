"""The countries plotted in the PPP figures, and their house-style colours.

Country codes and names come from :mod:`europe_data.countries` — the single curated
source in this repository — so nothing is duplicated here. This module only decides
*which* of those countries appear on the PPP charts and in what colour.
"""

from __future__ import annotations

from typing import NamedTuple

from europe_data import countries
from vizstyle import ACCENT, BLUE, GOLD, GREEN, MUTED, TEXT


class Peer(NamedTuple):
    iso3: str
    label: str        # the label drawn on the chart (may be shorter than the full name)
    colour: str
    linestyle: str
    linewidth: float


UK = "GBR"
US = "USA"

# The UK is always terracotta and heavier than everything else; the US is near-black as
# the primary comparator. Poland is included because it is the clearest case where PPP
# and market exchange rates tell materially different stories.
PEERS: list[Peer] = [
    Peer("GBR", "United Kingdom", ACCENT, "-", 2.8),
    Peer("USA", "United States", TEXT, "-", 1.9),
    Peer("DEU", "Germany", BLUE, "-", 1.9),
    Peer("FRA", "France", GOLD, "-", 1.9),
    Peer("ITA", "Italy", GREEN, "-", 1.9),
]

# Peers used on the "relative to the UK" chart. The UK itself is the 100% baseline there,
# so it is not in this list; Poland is added because its convergence is the headline.
RELATIVE_PEERS: list[Peer] = [
    Peer("USA", "United States", TEXT, "-", 2.8),
    Peer("DEU", "Germany", BLUE, "-", 2.0),
    Peer("FRA", "France", GOLD, "-", 2.0),
    Peer("EUU", "EU average", MUTED, "--", 2.0),
    Peer("POL", "Poland", GREEN, "-", 2.0),
]

# Peers on the price-level-index chart. The US is the numeraire (a flat 1.00 reference),
# so it is drawn as a horizontal guide rather than a series.
PRICE_LEVEL_PEERS: list[Peer] = [
    Peer("GBR", "United Kingdom", ACCENT, "-", 2.8),
    Peer("DEU", "Germany", BLUE, "-", 1.9),
    Peer("FRA", "France", GOLD, "-", 1.9),
    Peer("ITA", "Italy", GREEN, "-", 1.9),
    Peer("POL", "Poland", MUTED, "-", 1.9),
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
