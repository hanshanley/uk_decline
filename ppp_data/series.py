"""Small pure helpers for slicing tidy PPP rows into per-country series and ratios.

Kept separate from the chart code so that the arithmetic behind every figure can be unit
tested offline, and so that :mod:`ppp_data.validate` and :mod:`ppp_data.charts` share one
implementation rather than two subtly different ones.
"""

from __future__ import annotations

from typing import Iterable

from . import metrics


def index(rows: Iterable[dict]) -> dict[tuple[str, str, int], float]:
    """Index tidy rows by ``(metric, iso3, year)``."""
    return {(r["metric"], r["iso3"], r["year"]): r["value"] for r in rows}


def series(rows: Iterable[dict], metric: str, iso3: str) -> dict[int, float]:
    """``{year: value}`` for one country and metric."""
    return {
        r["year"]: r["value"]
        for r in rows
        if r["metric"] == metric and r["iso3"] == iso3
    }


def ratio(rows: Iterable[dict], metric: str, numerator: str, denominator: str,
          *, check: bool = True) -> dict[int, float]:
    """``{year: numerator/denominator}`` for one metric, over the overlapping years.

    By default the metric must be declared valid for same-year cross-country comparison,
    which rules out the constant-price PPP series.

    ``check=False`` is a deliberate escape hatch for the constant-price series, whose
    cross-country levels are anchored on the ICP benchmark year and extrapolated away from
    it. Three call sites use it, all deliberately and all labelled as volume rather than
    level comparisons: :func:`ppp_data.validate.check_benchmark_year_agreement` (which ratios
    it precisely to confirm it agrees with the current-price series in the benchmark year),
    and the two UK/US figures that plot real-volume divergence —
    :func:`ppp_data.charts.chart_ppp_vs_market_fx` and
    :func:`ppp_data.charts.uk_us_decomposition`. Do not use it to present a constant-price
    ratio as a same-year *level* comparison; that is what the guard exists to prevent.
    """
    if check:
        metrics.require_cross_section(metric)
    rows = list(rows)
    num = series(rows, metric, numerator)
    den = series(rows, metric, denominator)
    return {
        year: num[year] / den[year]
        for year in sorted(num.keys() & den.keys())
        if den[year]
    }


def years_between(data: dict[int, float], start: int | None = None,
                  end: int | None = None) -> list[int]:
    """Sorted years of ``data`` restricted to an optional inclusive range."""
    return [
        year for year in sorted(data)
        if (start is None or year >= start) and (end is None or year <= end)
    ]


def xy(data: dict[int, float], start: int | None = None,
       end: int | None = None) -> tuple[list[int], list[float]]:
    """Plot-ready ``(years, values)`` for a ``{year: value}`` mapping."""
    years = years_between(data, start, end)
    return years, [data[y] for y in years]
