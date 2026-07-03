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
    wb_indicator: str | None  # None for metrics derived locally (not a WB series)
    description: str


SOURCE = "World Bank WDI"

# US CPI used to deflate the nominal (current-US$) market-cap series to real terms.
CPI_INDICATOR = "FP.CPI.TOTL"  # Consumer price index, USA (World Bank, 2010 = 100)
CPI_SOURCE = "World Bank (FP.CPI.TOTL, US CPI)"

METRICS: dict[str, Metric] = {
    "market_cap_usd": Metric(
        "market_cap_usd",
        "Stock-market capitalisation (nominal)",
        "current US$",
        "CM.MKT.LCAP.CD",
        description=(
            "Total market value of listed domestic companies, in current (nominal) US "
            "dollars converted at market exchange rates (not PPP). The headline measure "
            "of absolute size, but not inflation-adjusted."
        ),
    ),
    "market_cap_usd_real": Metric(
        "market_cap_usd_real",
        "Stock-market capitalisation (real)",
        "constant US$",
        None,  # derived: market_cap_usd deflated by US CPI (see combine/deflator)
        description=(
            "The nominal market-cap series deflated by US CPI to constant US dollars, so "
            "sizes are comparable across years after removing US-dollar inflation. Values "
            "stay at market exchange rates (constant dollars, not PPP)."
        ),
    ),
    "market_cap_pct_gdp": Metric(
        "market_cap_pct_gdp",
        "Stock-market cap-to-GDP ratio",
        "% of GDP",
        "CM.MKT.LCAP.GD.ZS",
        description=(
            "Market capitalisation of listed domestic companies as a share of GDP -- "
            "the size of the market relative to the wider economy. A same-year ratio, "
            "so it is inflation-neutral by construction."
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

# indicator id -> metric id (reverse lookup for the fetcher; derived metrics excluded).
BY_INDICATOR: dict[str, str] = {
    m.wb_indicator: m.id for m in METRICS.values() if m.wb_indicator
}

# Short, per-metric caveats surfaced in the README and the trend summary.
CAVEATS: dict[str, str] = {
    "market_cap_usd": (
        "Compiled by the World Bank from S&P Global / World Federation of Exchanges "
        "data. Denominated in current (nominal) US$, so it blends local-currency "
        "valuation, USD exchange-rate moves, and inflation. The WDI series has "
        "tail-year gaps -- the UK is missing after 2022 -- so recent years may be "
        "blank; values are not spliced. See the real series for the inflation-adjusted view."
    ),
    "market_cap_usd_real": (
        "Derived: the nominal current-US$ series deflated by US CPI (World Bank "
        "FP.CPI.TOTL) to constant US dollars of the base year noted in the manifest/"
        "summary. This uses market exchange rates, i.e. constant dollars -- NOT PPP, "
        "which would distort market values by adjusting for domestic price levels. It "
        "removes US-dollar inflation; for non-US markets it does not remove exchange-rate "
        "effects. Only years with both market-cap and CPI data are computed (US CPI ends "
        "2024), so the newest year may be absent."
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

# Formal data provenance: the organization that actually collected each series, the
# database it lives in, and the World Bank indicator that redistributes it. Sourced
# from the World Bank indicator metadata (`sourceOrganization`). Used to build proper
# citations in the figures, summary, README, and manifest.
CITATIONS: dict[str, dict[str, str]] = {
    "market_cap_usd": {
        "collector": "World Federation of Exchanges (WFE)",
        "database": "WFE database",
        "indicator": "Market capitalization of listed domestic companies (current US$)",
        "code": "CM.MKT.LCAP.CD",
        "distributor": "World Bank, World Development Indicators",
        "url": "https://data.worldbank.org/indicator/CM.MKT.LCAP.CD",
    },
    "market_cap_pct_gdp": {
        "collector": "World Federation of Exchanges (WFE)",
        "database": "WFE database",
        "indicator": "Market capitalization of listed domestic companies (% of GDP)",
        "code": "CM.MKT.LCAP.GD.ZS",
        "distributor": "World Bank, World Development Indicators",
        "url": "https://data.worldbank.org/indicator/CM.MKT.LCAP.GD.ZS",
    },
    "listed_domestic_companies": {
        "collector": "World Federation of Exchanges (WFE)",
        "database": "WFE database",
        "indicator": "Listed domestic companies, total",
        "code": "CM.MKT.LDOM.NO",
        "distributor": "World Bank, World Development Indicators",
        "url": "https://data.worldbank.org/indicator/CM.MKT.LDOM.NO",
    },
    "cpi": {
        "collector": "International Monetary Fund (IMF)",
        "database": "International Financial Statistics",
        "indicator": "Consumer price index, United States (2010 = 100)",
        "code": "FP.CPI.TOTL",
        "distributor": "World Bank, World Development Indicators",
        "url": "https://data.worldbank.org/indicator/FP.CPI.TOTL",
    },
}


def _citation_keys(metric_id: str) -> list[str]:
    """Which CITATIONS entries back a metric (the real series combines two)."""
    if metric_id == "market_cap_usd_real":
        return ["market_cap_usd", "cpi"]
    return [metric_id]


def citation(metric_id: str, accessed: str | None = None) -> str:
    """Full formal citation(s) for a metric, naming the collecting organization.

    Example: 'World Federation of Exchanges (WFE), WFE database. Market
    capitalization of listed domestic companies (current US$) (CM.MKT.LCAP.CD).
    Distributed by World Bank, World Development Indicators.
    https://data.worldbank.org/indicator/CM.MKT.LCAP.CD (accessed 2026-07-03).'
    """
    parts: list[str] = []
    for key in _citation_keys(metric_id):
        c = CITATIONS[key]
        tail = f" (accessed {accessed})." if accessed else "."
        parts.append(
            f"{c['collector']}, {c['database']}. {c['indicator']} ({c['code']}). "
            f"Distributed by {c['distributor']}. {c['url']}{tail}"
        )
    return " ".join(parts)


def citation_short(metric_id: str, accessed: str | None = None) -> str:
    """Compact source attribution for a figure footnote, naming the collector(s)."""
    collectors: list[str] = []
    codes: list[str] = []
    for key in _citation_keys(metric_id):
        c = CITATIONS[key]
        if c["collector"] not in collectors:
            collectors.append(c["collector"])
        codes.append(c["code"])
    tail = f"; accessed {accessed}" if accessed else ""
    return (
        f"Data: {' & '.join(collectors)}, via World Bank World Development "
        f"Indicators ({', '.join(codes)}{tail})."
    )


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


def deflate_to_real(
    nominal_rows: list[dict], cpi: dict[int, float]
) -> tuple[list[dict], int | None]:
    """Deflate nominal ``market_cap_usd`` rows to real ``market_cap_usd_real`` rows.

    Uses the US CPI mapping ``{year: index}`` (World Bank ``FP.CPI.TOTL``). All
    figures are rebased to the **latest year present in both** ``cpi`` and the data,
    so real values are expressed in that base year's US dollars. Rows whose year has
    no CPI observation are skipped (never fabricated). Returns ``(real_rows, base_year)``;
    ``base_year`` is ``None`` if nothing could be deflated.
    """
    src = [r for r in nominal_rows if r["metric"] == "market_cap_usd"]
    if not src or not cpi:
        return [], None
    usable_years = {r["year"] for r in src} & set(cpi)
    if not usable_years:
        return [], None
    base_year = max(usable_years)
    base_cpi = cpi[base_year]
    real_rows: list[dict] = []
    for r in src:
        year_cpi = cpi.get(r["year"])
        if year_cpi is None or year_cpi == 0:
            continue
        real_value = r["value"] * (base_cpi / year_cpi)
        real_rows.append(
            make_row(
                r["region"],
                r["region_code"],
                r["year"],
                "market_cap_usd_real",
                real_value,
                source=f"{SOURCE} + {CPI_SOURCE}",
            )
        )
    return real_rows, base_year
