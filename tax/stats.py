"""Aggregation: UK vs the median/average European country vs the US, per metric.

For each metric variant we take a single target year (the latest with data) and report
the UK value, the US value, and the **median** and **mean** across European countries —
directly answering "how does the UK's tax burden compare on average / at the median".
"""

from __future__ import annotations

import statistics
from typing import Iterable, Optional

from . import config


def _variant(row: dict) -> tuple[str, str, str]:
    return (row["metric"], row["household"], row["earnings"])


def _target_year(recs: list[dict], year: Optional[int]) -> Optional[int]:
    """Pick the comparison year: explicit ``year``, else the latest with UK (then US) data.

    Falling back to the global max only when neither the UK nor the US is present avoids
    pinning a ragged latest OECD vintage that would blank the UK/US and shrink the
    European sample.
    """
    if year is not None:
        return year
    for iso3 in (config.UK_COUNTRY.iso3, config.US_COUNTRY.iso3):
        years = [r["year"] for r in recs if r["iso3"] == iso3]
        if years:
            return max(years)
    all_years = [r["year"] for r in recs]
    return max(all_years) if all_years else None


def summarize(rows: Iterable[dict], year: Optional[int] = None) -> list[dict]:
    """Summarise each metric variant into UK / US / Europe median & mean.

    ``year`` pins the comparison year; when ``None`` each variant independently uses the
    latest year for which the UK (then US) reports data. Returns a list of dict rows
    sorted by metric.
    """
    by_variant: dict[tuple[str, str, str], list[dict]] = {}
    for r in rows:
        by_variant.setdefault(_variant(r), []).append(r)

    out: list[dict] = []
    for variant, recs in by_variant.items():
        metric, household, earnings = variant
        target = _target_year(recs, year)
        if target is None:
            continue
        year_recs = [r for r in recs if r["year"] == target]
        if not year_recs:
            continue

        by_iso = {r["iso3"]: r["value"] for r in year_recs}
        europe = [
            r["value"] for r in year_recs if r["region"] == config.EUR
        ]
        out.append(
            {
                "metric": metric,
                "label": config.METRICS[metric].label,
                "household": household,
                "earnings": earnings,
                "year": target,
                "unit": config.METRICS[metric].unit,
                "uk": by_iso.get(config.UK_COUNTRY.iso3),
                "us": by_iso.get(config.US_COUNTRY.iso3),
                "europe_median": statistics.median(europe) if europe else None,
                "europe_mean": statistics.fmean(europe) if europe else None,
                "europe_n": len(europe),
            }
        )

    out.sort(key=lambda d: (d["metric"], d["household"], d["earnings"]))
    return out
