"""Aggregation helpers: median / average tuition per region.

Aggregation unit is **one figure per country** (unweighted), matching the
"UK has a higher average" framing. Zero-tuition countries (several EU states charge
no fee for domestic students) are legitimate data points and are kept.
"""

from __future__ import annotations

import statistics
from typing import Iterable, Optional, Sequence

from .config import DEGREE_YEARS


def average(values: Sequence[float]) -> Optional[float]:
    return statistics.fmean(values) if values else None


def round_or_none(value: Optional[float], ndigits: int = 2) -> Optional[float]:
    """Round ``value`` to ``ndigits``, preserving ``None`` (for absent metrics)."""
    return None if value is None else round(value, ndigits)


def median(values: Sequence[float]) -> Optional[float]:
    return statistics.median(values) if values else None


def aggregate_by_region(
    records: Iterable[dict],
    value_key: str,
    region_key: str = "region",
    degree_years: int = DEGREE_YEARS,
) -> dict[str, dict]:
    """Group ``records`` by region and compute count, mean & median for ``value_key``.

    Each region also gets the four-year totals (annual stat x ``degree_years``).
    Records whose ``value_key`` is ``None`` are skipped for that metric.
    """
    buckets: dict[str, list[float]] = {}
    for rec in records:
        val = rec.get(value_key)
        if val is None:
            continue
        buckets.setdefault(rec[region_key], []).append(float(val))

    out: dict[str, dict] = {}
    for region, values in buckets.items():
        mean_annual = average(values)
        median_annual = median(values)
        out[region] = {
            "n": len(values),
            "mean_annual": mean_annual,
            "median_annual": median_annual,
            "mean_4yr": None if mean_annual is None else mean_annual * degree_years,
            "median_4yr": None if median_annual is None else median_annual * degree_years,
        }
    return out
