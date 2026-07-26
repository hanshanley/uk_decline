"""World Bank WDI client for the PPP analysis.

Pulls the five World Bank series the PPP view needs — GDP per capita at PPP (constant and
current international $), GDP per capita at market exchange rates (current US$), the PPP
conversion factor, and the market exchange rate — and derives three more locally:

* ``price_level_index``        = ``NY.GDP.PCAP.CD / NY.GDP.PCAP.PP.CD``. Algebraically this
  is the PPP conversion factor over the market exchange rate, but computed this way the
  country's local-currency GDP cancels, so it survives redenominations. See
  :func:`derive_price_level_index`.
* ``price_level_index_direct`` = ``PA.NUS.PPP / PA.NUS.FCRF``, the textbook formula, kept
  **only** as a cross-check and never plotted — the two indicators do not share a currency
  basis for euro-area countries before 1999.
* ``gdp_per_capita_real_usd``  = current US$ GDP per capita deflated by US CPI.

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

# A hard ceiling on the paging loop. At 1,000 rows a page the real requests need one or two
# pages; this only bounds a degenerate response that keeps advertising more.
MAX_PAGES = 50

SOURCE = "World Bank WDI"
REAL_USD_SOURCE = "World Bank WDI (NY.GDP.PCAP.CD deflated by US CPI, FP.CPI.TOTL)"
DERIVED_PLI_SOURCE = "Derived: World Bank WDI NY.GDP.PCAP.CD / NY.GDP.PCAP.PP.CD"
DERIVED_PLI_DIRECT_SOURCE = "Derived: World Bank WDI PA.NUS.PPP / PA.NUS.FCRF"


def _fetch_indicator(indicator: str, iso3s: list[str], start: int, end: int) -> Iterator[dict]:
    """Yield tidy rows for one indicator, following the API's paging.

    The page count comes from the remote payload, so it is treated as untrusted: the loop
    stops on a malformed header, on a page that yields no rows, and at a hard ceiling, so a
    degenerate upstream response cannot drive unbounded requests.
    """
    metric_id = metrics.BY_INDICATOR[indicator]
    codes = ";".join(iso3s)
    page = 1
    while page <= MAX_PAGES:
        payload = get_json(
            f"{BASE}/country/{codes}/indicator/{indicator}",
            params={"format": "json", "per_page": 1000,
                    "date": f"{start}:{end}", "page": page},
        )
        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            return
        meta, rows = payload[0], payload[1]
        if not rows:
            return
        for row in rows:
            value = row.get("value")
            iso3 = row.get("countryiso3code") or ""
            if value is None or not iso3:
                continue
            yield metrics.make_row(
                iso3, peers.name_for(iso3), int(row["date"]), metric_id, float(value)
            )
        try:
            pages = int(meta.get("pages", 1)) if isinstance(meta, dict) else 1
        except (TypeError, ValueError):
            return  # a malformed page count: stop rather than loop on a bad response
        if page >= pages:
            return
        page += 1


def derive_price_level_index(rows: Iterable[dict]) -> list[dict]:
    """Derive the price level index, currency-unit-free, from the two GDP-per-capita series.

    ``PLI = GDPpc(current US$) / GDPpc(current international $)``. Algebraically this is the
    PPP conversion factor over the market exchange rate, but computed this way the country's
    local-currency GDP cancels out, so the result survives redenominations and the euro
    changeover — unlike the direct ratio of the two conversion-factor indicators, which the
    World Bank does not always quote in the same currency. See
    :func:`derive_price_level_index_direct` and ``validate.CURRENCY_BASIS_BREAKS``.

    Only country-years with **both** inputs present produce an index; nothing is filled in.
    """
    return _derive_ratio(
        rows,
        numerator="gdp_per_capita_nominal_usd",
        denominator="gdp_per_capita_ppp_current",
        metric_id="price_level_index",
        source=DERIVED_PLI_SOURCE,
    )


def derive_price_level_index_direct(rows: Iterable[dict]) -> list[dict]:
    """Derive the same index straight from the conversion factors, as a cross-check.

    ``PA.NUS.PPP / PA.NUS.FCRF``. This is the textbook definition, and it agrees with
    :func:`derive_price_level_index` wherever the two indicators share a currency basis —
    which is everywhere except euro-area countries before 1999. It is never plotted; it
    exists so that :mod:`ppp_data.validate` can confirm the headline index from two
    completely independent pairs of World Bank series.
    """
    return _derive_ratio(
        rows,
        numerator="ppp_conversion_factor",
        denominator="market_exchange_rate",
        metric_id="price_level_index_direct",
        source=DERIVED_PLI_DIRECT_SOURCE,
    )


def _derive_ratio(rows: Iterable[dict], *, numerator: str, denominator: str,
                  metric_id: str, source: str) -> list[dict]:
    """Build a derived metric as the per-country-year ratio of two fetched metrics."""
    num: dict[tuple[str, int], float] = {}
    den: dict[tuple[str, int], float] = {}
    names: dict[str, str] = {}
    for row in rows:
        key = (row["iso3"], row["year"])
        names[row["iso3"]] = row["country"]
        if row["metric"] == numerator:
            num[key] = row["value"]
        elif row["metric"] == denominator:
            den[key] = row["value"]

    out: list[dict] = []
    for key in sorted(num.keys() & den.keys()):
        iso3, year = key
        divisor = den[key]
        if not divisor:  # a zero here is a corrupt upstream row, not a datum
            continue
        out.append(
            metrics.make_row(iso3, names[iso3], year, metric_id,
                             num[key] / divisor, source=source)
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
    """Fetch every World Bank series the PPP analysis needs, plus the derived ones."""
    rows: list[dict] = []
    for indicator in GDP_INDICATORS:
        rows.extend(_fetch_indicator(indicator, peers.ALL_ISO3, start, end))
    for indicator in CONVERSION_INDICATORS:
        rows.extend(_fetch_indicator(indicator, peers.COUNTRY_ISO3, start, end))
    rows.extend(derive_price_level_index(rows))
    rows.extend(derive_price_level_index_direct(rows))
    rows.extend(derive_real_usd(rows, start, end))
    return rows
