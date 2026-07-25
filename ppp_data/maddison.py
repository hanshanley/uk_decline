"""Maddison Project Database rows, re-labelled onto this package's metric registry.

The long-run PPP series is fetched by :mod:`europe_data.maddison` (Maddison Project
Database 2023 via Our World in Data). This wrapper exists only to normalise the unit string
onto ``ppp_data.metrics``; the fetch itself is not duplicated.

Maddison is expressed in **2011** international dollars, a different benchmark from the
World Bank's ICP 2021 series, so it is charted on its own and never joined to a World Bank
line.
"""

from __future__ import annotations

from europe_data import maddison as _europe_maddison

from . import metrics, peers

METRIC = "gdp_per_capita_real_maddison"
SOURCE = _europe_maddison.SOURCE


def fetch(start: int, end: int) -> list[dict]:
    """Fetch long-run Maddison GDP per capita for the plotted countries."""
    rows = _europe_maddison.fetch(start, end, iso3s=peers.COUNTRY_ISO3)
    unit = metrics.METRICS[METRIC].unit
    return [{**row, "unit": unit} for row in rows]
