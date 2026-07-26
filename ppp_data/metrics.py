"""Canonical PPP metric registry, units, vintages, and per-metric caveats.

The central idea encoded here is that **a PPP series is only valid for one kind of
comparison at a time**, and mixing them up is the single easiest way to draw a wrong
conclusion:

``over_time``
    Safe to plot as a **level, across years**. Requires a constant-price series, i.e. one
    where general inflation has been removed (``NY.GDP.PCAP.PP.KD``, constant 2021
    international $). A *current* international-$ series is **not** safe here, because it
    embeds worldwide inflation — a rising line would partly be rising prices.

``cross_section``
    Safe to use for a **same-year, cross-country ratio**. Here the *current* series is the
    better choice: it converts each year's output at that year's price levels. The
    constant-price series is benchmarked on the ICP 2021 round and extrapolated away from
    it with each country's *own* GDP deflator, so its cross-country ratios drift as you
    move away from 2021.

Both flags are enforced by :func:`require_over_time` / :func:`require_cross_section`, which
the chart module calls before plotting, so a future edit cannot silently pick the wrong
series.
"""

from __future__ import annotations

from typing import NamedTuple


class Metric(NamedTuple):
    id: str
    label: str
    unit: str
    wb_indicator: str | None  # None => derived locally or sourced elsewhere
    over_time: bool           # valid as a level time series?
    cross_section: bool       # valid for a same-year cross-country ratio?
    vintage: str              # price/PPP benchmark this series is expressed on
    description: str
    validation_only: bool = False  # fetched to cross-check another metric, never plotted


SOURCE = "World Bank WDI"

# The International Comparison Program benchmark round underlying the World Bank's current
# PPP estimates. Every PPP figure must name it: levels shift retroactively when the World
# Bank re-benchmarks (2011 -> 2017 -> 2021), so figures from different vintages are NOT
# comparable and must never be spliced.
ICP_VINTAGE = "ICP 2021"

METRICS: dict[str, Metric] = {
    "gdp_per_capita_ppp_constant": Metric(
        "gdp_per_capita_ppp_constant",
        "Real GDP per capita at PPP",
        "constant 2021 international $",
        "NY.GDP.PCAP.PP.KD",
        over_time=True,
        cross_section=False,
        vintage=ICP_VINTAGE,
        description=(
            "GDP per capita converted at purchasing power parity and held at constant 2021 "
            "prices. Inflation is removed, so levels are comparable across years — this is "
            "the PPP analogue of the headline constant-US$ series. Cross-country ratios are "
            "extrapolated from the 2021 benchmark using each country's own GDP deflator, so "
            "use the current-price series for same-year comparisons."
        ),
    ),
    "gdp_per_capita_ppp_current": Metric(
        "gdp_per_capita_ppp_current",
        "GDP per capita at PPP (current prices)",
        "current international $",
        "NY.GDP.PCAP.PP.CD",
        over_time=False,
        cross_section=True,
        vintage=ICP_VINTAGE,
        description=(
            "GDP per capita converted at each year's PPP, in that year's prices. The correct "
            "basis for a same-year cross-country ratio, and the series that satisfies the "
            "exact identity GDPpc(current US$) = GDPpc(current int'l $) x price level index. "
            "It embeds worldwide inflation, so it must never be plotted as a level over time."
        ),
    ),
    "gdp_per_capita_real_usd": Metric(
        "gdp_per_capita_real_usd",
        "Real GDP per capita at market exchange rates",
        "constant 2015 US$",
        None,  # derived: NY.GDP.PCAP.CD deflated by US CPI (europe_data.worldbank)
        over_time=True,
        cross_section=True,
        vintage="US CPI 2015 base",
        description=(
            "The repository's headline measure, reproduced here as the comparator: GDP per "
            "capita in current US$ (NY.GDP.PCAP.CD) deflated by US CPI to constant 2015 US$. "
            "Market exchange rates are preserved, so sterling's moves are visible. Because a "
            "country-vs-country ratio cancels the common deflator, its cross-section ratios "
            "equal those of the underlying current-US$ series."
        ),
    ),
    "gdp_per_capita_nominal_usd": Metric(
        "gdp_per_capita_nominal_usd",
        "GDP per capita at market exchange rates (current prices)",
        "current US$",
        "NY.GDP.PCAP.CD",
        over_time=False,
        cross_section=True,
        vintage="current prices",
        description=(
            "GDP per capita converted at the year's market exchange rate, in that year's "
            "prices. Kept because it is the left-hand side of the PPP identity; not plotted "
            "as a level over time because it is not inflation-adjusted."
        ),
    ),
    "ppp_conversion_factor": Metric(
        "ppp_conversion_factor",
        "PPP conversion factor, GDP",
        "LCU per international $",
        "PA.NUS.PPP",
        over_time=False,
        cross_section=True,
        vintage=ICP_VINTAGE,
        description=(
            "How many units of local currency buy what one US dollar buys in the United "
            "States. The US is the numeraire, so its factor is 1.0 by construction."
        ),
    ),
    "market_exchange_rate": Metric(
        "market_exchange_rate",
        "Market exchange rate",
        "LCU per US$ (period average)",
        "PA.NUS.FCRF",
        over_time=False,
        cross_section=True,
        vintage="current prices",
        description=(
            "The official period-average market exchange rate. Paired with the PPP "
            "conversion factor it yields the price level index."
        ),
    ),
    "price_level_index": Metric(
        "price_level_index",
        "Price level index (US = 1.00)",
        "ratio, US = 1.00",
        None,  # derived: gdp_per_capita_nominal_usd / gdp_per_capita_ppp_current
        over_time=True,
        cross_section=True,
        vintage=ICP_VINTAGE,
        description=(
            "How expensive a country is relative to the United States. Above 1.00 its "
            "currency buys less at home than the market exchange rate implies; below 1.00, "
            "more. This single ratio is the entire difference between the market-FX and PPP "
            "views of GDP. Derived as GDP per capita in current US$ divided by GDP per "
            "capita in current international $ — algebraically the PPP conversion factor "
            "over the market exchange rate, but computed this way the local-currency units "
            "cancel, so it is immune to redenominations and currency changeovers. It is a "
            "unit-free ratio, so it is safe to plot over time."
        ),
    ),
    "price_level_index_direct": Metric(
        "price_level_index_direct",
        "Price level index, computed directly from the conversion factors",
        "ratio, US = 1.00",
        None,  # derived: ppp_conversion_factor / market_exchange_rate
        over_time=False,
        cross_section=False,
        vintage=ICP_VINTAGE,
        validation_only=True,
        description=(
            "The same quantity taken straight from PA.NUS.PPP / PA.NUS.FCRF. Kept purely as "
            "an independent cross-check on `price_level_index`, which is built from two "
            "entirely different World Bank series. It is NOT plotted, because the two "
            "indicators do not always share a currency basis: for euro-area countries "
            "before 1999 the World Bank restates the PPP conversion factor in euro while "
            "leaving the exchange rate in the legacy national currency, which makes the "
            "direct ratio wrong by the legacy conversion rate. See "
            "`validate.CURRENCY_BASIS_BREAKS`."
        ),
    ),
    "gdp_per_capita_real_maddison": Metric(
        "gdp_per_capita_real_maddison",
        "Real GDP per capita at PPP (Maddison)",
        "constant 2011 international $",
        None,  # sourced from the Maddison Project Database via europe_data.maddison
        over_time=True,
        cross_section=False,
        vintage="Maddison 2023 / ICP 2011",
        description=(
            "The Maddison Project Database's long-run real GDP-per-capita series, in 2011 "
            "international dollars. It is the only PPP series here that reaches back before "
            "1990, but it sits on a different (2011) benchmark from the World Bank series, "
            "so it must be shown on its own chart and never spliced onto a World Bank line."
        ),
    ),
}

# Column order for the wide table (one row per country-year).
METRIC_ORDER: list[str] = list(METRICS)

# indicator id -> metric id (derived metrics have no indicator).
BY_INDICATOR: dict[str, str] = {
    m.wb_indicator: m.id for m in METRICS.values() if m.wb_indicator
}

# Metrics fetched purely to cross-check another metric; never plotted.
VALIDATION_ONLY: frozenset[str] = frozenset(
    m.id for m in METRICS.values() if m.validation_only
)
# Metrics that may be plotted as a level across years.
TIME_SERIES_SAFE: frozenset[str] = frozenset(
    m.id for m in METRICS.values() if m.over_time
)
# Metrics that may be used for a same-year cross-country ratio.
CROSS_SECTION_SAFE: frozenset[str] = frozenset(
    m.id for m in METRICS.values() if m.cross_section
)

CAVEATS: dict[str, str] = {
    "gdp_per_capita_ppp_constant": (
        "Constant 2021 international dollars. Levels are comparable across years, but the "
        "series is anchored to the ICP 2021 benchmark and extrapolated with each country's "
        "own GDP deflator, so cross-country levels are most reliable near 2021 and drift "
        "the further you move from it. World Bank coverage begins in 1990."
    ),
    "gdp_per_capita_ppp_current": (
        "Current international dollars: correct for same-year cross-country ratios, wrong "
        "for trends, because it carries worldwide inflation. Never plotted as a level."
    ),
    "gdp_per_capita_real_usd": (
        "Market exchange rates, so it moves with sterling as well as with output. This is "
        "the point of the comparison, not a defect: it measures what UK output buys on "
        "world markets."
    ),
    "gdp_per_capita_nominal_usd": (
        "Not inflation-adjusted. Retained only as the left-hand side of the PPP identity."
    ),
    "ppp_conversion_factor": (
        "Re-benchmarked with each ICP round (2011, 2017, 2021); the World Bank revises the "
        "whole back-series when it re-benchmarks, so these values are not comparable with "
        "PPP figures published under an earlier vintage."
    ),
    "market_exchange_rate": (
        "Period-average, not end-of-year. A large intra-year currency move (2008, 2016, "
        "2022) is therefore smoothed across two calendar years."
    ),
    "price_level_index": (
        "Derived as GDP per capita in current US$ over GDP per capita in current "
        "international $. The local-currency GDP cancels, so the index is unaffected by "
        "redenominations or the euro changeover. It inherits the ICP vintage of the "
        "underlying parities. The US is the numeraire, so the US index is 1.00 in every "
        "year by construction."
    ),
    "price_level_index_direct": (
        "Validation-only. PA.NUS.PPP / PA.NUS.FCRF disagrees with the headline index for "
        "euro-area countries before 1999, because those two indicators are quoted in "
        "different currencies for those years. Never plotted."
    ),
    "gdp_per_capita_real_maddison": (
        "2011 international dollars — a different benchmark from the World Bank series. "
        "Shown on its own chart; never spliced onto a World Bank line."
    ),
}


def require_over_time(metric_id: str) -> Metric:
    """Return the metric, or raise if it must not be plotted as a level over time."""
    metric = METRICS[metric_id]
    if not metric.over_time:
        raise ValueError(
            f"{metric_id!r} is expressed in {metric.unit} and carries inflation; it cannot "
            "be plotted as a level across years. Use a constant-price metric "
            f"({', '.join(sorted(TIME_SERIES_SAFE))})."
        )
    return metric


def require_cross_section(metric_id: str) -> Metric:
    """Return the metric, or raise if it must not be used for a same-year ratio."""
    metric = METRICS[metric_id]
    if not metric.cross_section:
        raise ValueError(
            f"{metric_id!r} is a constant-price series extrapolated from its benchmark "
            "year, so same-year cross-country ratios are unreliable. Use a current-price "
            f"metric ({', '.join(sorted(CROSS_SECTION_SAFE))})."
        )
    return metric


def make_row(iso3: str, country: str, year: int, metric_id: str, value: float,
             source: str = SOURCE) -> dict:
    """Build one tidy long-format row in the repository-wide schema."""
    metric = METRICS[metric_id]
    return {
        "iso3": iso3,
        "country": country,
        "year": int(year),
        "metric": metric_id,
        "value": float(value),
        "unit": metric.unit,
        "source": source,
    }
