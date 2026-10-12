"""Derive the median age from the published World Bank 5-year age-band populations.

**This is a derivation, not a directly-published figure**, and every row it produces is
tagged ``source = config.SOURCE_WB_DERIVED`` so it can never be confused with an official
value. The method is the standard *grouped median* (linear interpolation of the cumulative
population distribution within the band that contains the 50th percentile):

    median = L + ((50 - CF_below) / f_band) * width

where, for the band containing the median, ``L`` is its lower age bound, ``CF_below`` is
the cumulative population percentage below ``L``, ``f_band`` is the band's percentage of
the population, and ``width`` is 5 years. This assumes a uniform distribution within
the median band. A median in the open-ended 80+ band cannot be interpolated.
It is fully reproducible from the same published band counts.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional

from . import config
from .combine import make_row

SOURCE = config.SOURCE_WB_DERIVED
METRIC = "median_age_years"
METRICS = (METRIC,)

# Ordered (band label, lower age bound). Lower bound = midpoint - half band width.
_ORDERED_BANDS: list[tuple[str, float]] = [
    (label, midpoint - config.BAND_WIDTH_YEARS / 2.0) for _code, label, midpoint in config.AGE_BANDS
]


def _median_from_band_shares(band_pct: dict[str, float]) -> Optional[float]:
    """Grouped-median age from ``{band_label: percent_of_total}`` (summed over sex)."""
    total = sum(band_pct.values())
    if total <= 0:
        return None
    # Normalise to exactly 100% so rounding in the source shares can't bias the crossing.
    scale = 100.0 / total
    cumulative = 0.0
    for label, lower in _ORDERED_BANDS:
        f_band = band_pct.get(label, 0.0) * scale
        if cumulative + f_band >= 50.0:
            if label == "80+":
                raise ValueError("cannot interpolate a median in the open-ended 80+ band")
            if f_band <= 0:
                return lower
            return lower + ((50.0 - cumulative) / f_band) * config.BAND_WIDTH_YEARS
        cumulative += f_band
    return None


def derive(band_share_rows: Iterable[dict]) -> list[dict]:
    """Derive medians from complete, unique age-band profiles for both sexes.

    Band shares are summed across sexes per country-year, then the grouped-median formula
    is applied. Input rows for other metrics are ignored.
    """
    grouped: dict[tuple[str, int], dict[tuple[str, str], float]] = {}
    expected = {(band, sex) for band in config.BAND_ORDER for sex in config.SEXES.values()}
    for r in band_share_rows:
        if r["metric"] != "pop_band_share_pct":
            continue
        key = (r["iso3"], r["year"])
        cells = grouped.setdefault(key, {})
        cell = (r["age_band"], r["sex"])
        if cell not in expected or cell in cells:
            raise ValueError(f"{key}: unknown or duplicate age/sex cell {cell}")
        value = float(r["value"])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{key}: invalid age-band share {value}")
        cells[cell] = value

    out: list[dict] = []
    for (iso3, year), cells in grouped.items():
        if set(cells) != expected:
            raise ValueError(f"{iso3} {year}: incomplete age/sex profile")
        if not math.isclose(sum(cells.values()), 100.0, abs_tol=0.01):
            raise ValueError(f"{iso3} {year}: age-band shares do not sum to 100%")
        band_pct = {
            band: sum(cells[(band, sex)] for sex in config.SEXES.values())
            for band in config.BAND_ORDER
        }
        median = _median_from_band_shares(band_pct)
        if median is None:
            continue
        out.append(
            make_row(
                iso3=iso3,
                year=year,
                metric=METRIC,
                value=round(median, 2),
                source=SOURCE,
            )
        )
    return out


def fetch(start: int, end: int, iso3s: Iterable[str] | None = None) -> list[dict]:
    """Standalone: fetch the 5-year band shares, then derive median age from them."""
    from . import pyramids

    return derive(pyramids.fetch(start, end, iso3s))
