"""Aggregation: UK vs the median/average European country vs the US, per metric.

For each metric variant and a target year (latest with UK data if unspecified) reports the
UK value, the US value, and the median & mean across European countries — answering "how
does the UK's age structure compare on average / at the median".
"""

from __future__ import annotations

import statistics
from typing import Iterable, Optional

from . import config


def _variant(row: dict) -> tuple[str, str, str]:
    return (row["metric"], row["age_band"], row["sex"])


def _target_year(recs: list[dict], year: Optional[int]) -> Optional[int]:
    """Explicit ``year``, else the latest year with UK (then US) data, else global max."""
    if year is not None:
        return year
    for iso3 in ("GBR", "USA"):
        years = [r["year"] for r in recs if r["iso3"] == iso3]
        if years:
            return max(years)
    all_years = [r["year"] for r in recs]
    return max(all_years) if all_years else None


def summarize(rows: Iterable[dict], year: Optional[int] = None) -> list[dict]:
    """Summarise each metric variant into UK / US / Europe median & mean."""
    by_variant: dict[tuple[str, str, str], list[dict]] = {}
    for r in rows:
        by_variant.setdefault(_variant(r), []).append(r)

    out: list[dict] = []
    for (metric, age_band, sex), recs in by_variant.items():
        target = _target_year(recs, year)
        if target is None:
            continue
        year_recs = [r for r in recs if r["year"] == target]
        if not year_recs:
            continue
        by_iso = {r["iso3"]: r["value"] for r in year_recs}
        europe = [r["value"] for r in year_recs if r["region"] == config.EUR]
        out.append(
            {
                "metric": metric,
                "label": config.METRICS[metric].label,
                "age_band": age_band,
                "sex": sex,
                "year": target,
                "unit": config.METRICS[metric].unit,
                "uk": by_iso.get("GBR"),
                "us": by_iso.get("USA"),
                "europe_median": statistics.median(europe) if europe else None,
                "europe_mean": statistics.fmean(europe) if europe else None,
                "europe_n": len(europe),
            }
        )

    out.sort(key=lambda d: (d["metric"], d["age_band"], d["sex"]))
    return out
