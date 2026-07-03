"""Canonical stock-market-size metrics, the tidy-row schema, and caveats.

Three complementary World Bank WDI measures of the *size* of a stock market:

* ``market_cap_usd``           -- absolute size in current US$.
* ``market_cap_pct_gdp``       -- size relative to the economy (% of GDP).
* ``listed_domestic_companies``-- breadth: number of listed domestic firms.

Each row carries its ``source`` and each metric carries a caveat, so downstream
charts/summaries can be honest about comparability (see :data:`CAVEATS`).
"""

from __future__ import annotations

from typing import Any, NamedTuple

# Tidy long-format row schema returned by every source module.
ROW_FIELDS: tuple[str, ...] = (
    "region",       # full name, e.g. "United Kingdom"
    "region_code",  # World Bank code, e.g. GBR / USA / WLD
    "year",         # calendar year (int)
    "metric",       # canonical metric id (see METRICS)
    "value",        # float
    "unit",         # unit label
    "source",       # source attribution string
)


class Metric(NamedTuple):
    id: str
    label: str
    unit: str
    wb_indicator: str
    description: str


SOURCE = "World Bank WDI"

METRICS: dict[str, Metric] = {
    "market_cap_usd": Metric(
        "market_cap_usd",
        "Stock-market capitalisation",
        "current US$",
        "CM.MKT.LCAP.CD",
        description=(
            "Total market value of listed domestic companies, in current US dollars. "
            "The headline measure of the absolute size of a national stock market."
        ),
    ),
    "market_cap_pct_gdp": Metric(
        "market_cap_pct_gdp",
        "Stock-market cap-to-GDP ratio",
        "% of GDP",
        "CM.MKT.LCAP.GD.ZS",
        description=(
            "Market capitalisation of listed domestic companies as a share of GDP -- "
            "the size of the market relative to the wider economy."
        ),
    ),
    "listed_domestic_companies": Metric(
        "listed_domestic_companies",
        "Listed domestic companies",
        "companies",
        "CM.MKT.LDOM.NO",
        description=(
            "Number of domestically incorporated companies listed on the country's "
            "stock exchanges at year end (excludes investment funds and foreign firms)."
        ),
    ),
}

# indicator id -> metric id (reverse lookup for the fetcher).
BY_INDICATOR: dict[str, str] = {m.wb_indicator: m.id for m in METRICS.values()}

# Short, per-metric caveats surfaced in the README and the trend summary.
CAVEATS: dict[str, str] = {
    "market_cap_usd": (
        "Compiled by the World Bank from S&P Global / World Federation of Exchanges "
        "data. Denominated in current US$, so it blends local-currency valuation and "
        "USD exchange-rate moves. The WDI series has tail-year gaps -- the UK is "
        "missing after 2022 -- so recent years may be blank; values are not spliced."
    ),
    "market_cap_pct_gdp": (
        "The more comparable 'size relative to the economy' measure, but sensitive to "
        "the denominator: countries with many large foreign-listed firms (e.g. the UK) "
        "can look large relative to domestic GDP."
    ),
    "listed_domestic_companies": (
        "Counts domestic listings only; delistings, M&A, and take-private activity "
        "reduce the count even as market value rises. Compare trends, not raw counts, "
        "across exchanges with different listing rules."
    ),
}


def make_row(
    region: str,
    region_code: str,
    year: int,
    metric: str,
    value: float,
    source: str = SOURCE,
) -> dict[str, Any]:
    """Build a validated tidy row, deriving the unit from the metric id."""
    if metric not in METRICS:
        raise KeyError(f"unknown metric id: {metric!r}")
    return {
        "region": region,
        "region_code": region_code,
        "year": int(year),
        "metric": metric,
        "value": float(value),
        "unit": METRICS[metric].unit,
        "source": source,
    }


def format_usd(value: float | None) -> str:
    """Format a US$ amount compactly (``$3.10T`` / ``$704B`` / ``$1,234``).

    Shared by the charts (axis ticks) and the summary so the same value renders
    at the same precision everywhere.
    """
    if value is None:
        return "n/a"
    if abs(value) >= 1e12:
        return f"${value / 1e12:.2f}T"
    if abs(value) >= 1e9:
        return f"${value / 1e9:.0f}B"
    return f"${value:,.0f}"


def uk_us_ratio(metric_rows):
    """UK-as-a-share-of-US ratio (a fraction) indexed by year, or ``None``.

    ``metric_rows`` is a long-format DataFrame already filtered to a single metric.
    Returns a pandas Series of GBR/USA for years where both exist and the ratio is
    finite; ``None`` if either region is absent or nothing overlaps. Non-finite
    values (e.g. a zero US denominator) are dropped so peak/latest stay meaningful.
    """
    import numpy as np
    import pandas as pd

    piv = metric_rows.pivot_table(
        index="year", columns="region_code", values="value", aggfunc="first"
    )
    if "GBR" not in piv.columns or "USA" not in piv.columns:
        return None
    ratio = (piv["GBR"] / piv["USA"]).replace([np.inf, -np.inf], pd.NA).dropna()
    return ratio if not ratio.empty else None
