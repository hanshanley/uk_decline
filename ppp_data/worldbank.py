"""World Bank WDI client for the PPP analysis.

Pulls the five World Bank series the PPP view needs — GDP per capita at PPP (constant and
current international $), GDP per capita at market exchange rates (current US$), the PPP
conversion factor, and the market exchange rate — and derives two more locally:

* ``price_level_index``    = PPP conversion factor / market exchange rate
* ``gdp_per_capita_real_usd`` = current US$ GDP per capita deflated by US CPI

The deflation is delegated to :func:`europe_data.worldbank.deflate_to_real_usd`, the exact
function behind the repository's headline chart, so the market-FX comparator plotted here
is arithmetically identical to the headline series rather than a re-implementation of it.

No API key is required. Results are paged; only non-null observations are emitted, and
nothing is interpolated, forward-filled, or spliced.
"""

from __future__ import annotations

from typing import Iterable, Iterator

from europe_data import worldbank as _europe_worldbank
from europe_data._http import get_json

from . import metrics, peers

BASE = "https://api.worldbank.org/v2"

# World Bank indicators fetched for every plotted entity, including aggregates like the EU.
GDP_INDICATORS: tuple[str, ...] = (
    "NY.GDP.PCAP.PP.KD",  # -> gdp_per_capita_ppp_constant
    "NY.GDP.PCAP.PP.CD",  # -> gdp_per_capita_ppp_current
    "NY.GDP.PCAP.CD",     # -> gdp_per_capita_nominal_usd
)

# Conversion factors, fetched for countries only: a multi-currency aggregate such as the
# EU has no single exchange rate, so a "price level" for it would be meaningless.
CONVERSION_INDICATORS: tuple[str, ...] = (
    "PA.NUS.PPP",    # -> ppp_conversion_factor
    "PA.NUS.FCRF",   # -> market_exchange_rate
)

# The World Bank's PPP-based GDP series begin in 1990; earlier PPP coverage only exists in
# the Maddison Project Database, which sits on a different benchmark and gets its own chart.
PPP_FIRST_YEAR = 1990

SOURCE = "World Bank WDI"
REAL_USD_SOURCE = "World Bank WDI (NY.GDP.PCAP.CD deflated by US CPI, FP.CPI.TOTL)"
DERIVED_PLI_SOURCE = "Derived: World Bank WDI PA.NUS.PPP / PA.NUS.FCRF"


def _fetch_indicator(indicator: str, iso3s: list[str], start: int, end: int) -> Iterator[dict]:
    """Yield tidy rows for one indicator, following the API's paging."""
    metric_id = metrics.BY_INDICATOR[indicator]
    codes = ";".join(iso3s)
    page = 1
    while True:
        payload = get_json(
            f"{BASE}/country/{codes}/indicator/{indicator}",
            params={"format": "json", "per_page": 1000,
                    "date": f"{start}:{end}", "page": page},
        )
        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            return
        meta, rows = payload[0], payload[1]
        for row in rows:
            value = row.get("value")
            iso3 = row.get("countryiso3code") or ""
            if value is None or not iso3:
                continue
            yield metrics.make_row(
                iso3, peers.name_for(iso3), int(row["date"]), metric_id, float(value)
            )
        if page >= int(meta.get("pages", 1)):
            return
        page += 1


def derive_price_level_index(rows: Iterable[dict]) -> list[dict]:
    """Derive the price level index from the PPP conversion factor and the exchange rate.

    ``PLI = PA.NUS.PPP / PA.NUS.FCRF`` — how expensive a country is relative to the United
    States, which is the numeraire and therefore 1.00 in every year. Only country-years
    with **both** inputs present produce an index; nothing is filled in.
    """
    ppp: dict[tuple[str, int], float] = {}
    fx: dict[tuple[str, int], float] = {}
    names: dict[str, str] = {}
    for row in rows:
        key = (row["iso3"], row["year"])
        names[row["iso3"]] = row["country"]
        if row["metric"] == "ppp_conversion_factor":
            ppp[key] = row["value"]
        elif row["metric"] == "market_exchange_rate":
            fx[key] = row["value"]

    out: list[dict] = []
    for key in sorted(ppp.keys() & fx.keys()):
        iso3, year = key
        rate = fx[key]
        if not rate:  # a zero exchange rate would be a corrupt upstream row, not a datum
            continue
        out.append(
            metrics.make_row(iso3, names[iso3], year, "price_level_index",
                             ppp[key] / rate, source=DERIVED_PLI_SOURCE)
        )
    return out


def derive_real_usd(rows: Iterable[dict], start: int, end: int) -> list[dict]:
    """Derive constant-2015-US$ GDP per capita, reusing the headline chart's deflator.

    Delegates the arithmetic to :func:`europe_data.worldbank.deflate_to_real_usd` so this
    comparator series is identical to the one in ``outputs/gdp_income/``, then normalises
    the unit string onto this package's metric registry.
    """
    nominal = [r for r in rows if r["metric"] == "gdp_per_capita_nominal_usd"]
    if not nominal:
        return []
    cpi = _europe_worldbank.us_cpi(start, end)
    deflated = _europe_worldbank.deflate_to_real_usd(nominal, cpi)
    unit = metrics.METRICS["gdp_per_capita_real_usd"].unit
    return [{**r, "unit": unit, "source": REAL_USD_SOURCE} for r in deflated]


def fetch(start: int = PPP_FIRST_YEAR, end: int = 2024) -> list[dict]:
    """Fetch every World Bank series the PPP analysis needs, plus the two derived ones."""
    rows: list[dict] = []
    for indicator in GDP_INDICATORS:
        rows.extend(_fetch_indicator(indicator, peers.ALL_ISO3, start, end))
    conversion: list[dict] = []
    for indicator in CONVERSION_INDICATORS:
        conversion.extend(_fetch_indicator(indicator, peers.COUNTRY_ISO3, start, end))
    rows.extend(conversion)
    rows.extend(derive_price_level_index(conversion))
    rows.extend(derive_real_usd(rows, start, end))
    return rows
