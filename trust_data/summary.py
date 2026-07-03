"""Summarise the UK trust trend from the combined long table.

For each metric this computes, using only rows present in ``trust_combined_long.csv``:
  * the UK's earliest and latest observed value (and years),
  * the absolute change and direction over that span,
  * the UK's latest value vs the EU-27 mean and the US, at the UK's latest year.

Writes ``data/trust/processed/trust_summary.csv`` and prints a readable table. The survey
percentage and the WGI estimates are not comparable across metrics (see
:data:`trust_data.metrics.CAVEATS`); read each row within its own metric.
"""

from __future__ import annotations

import csv
import os
import statistics
from typing import Optional

from . import countries, metrics
from .paths import DEFAULT_LONG_CSV, PROCESSED_DIR, SUMMARY_CSV


def load_rows(path: str | None = None) -> list[dict]:
    path = path or DEFAULT_LONG_CSV
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["year"] = int(r["year"])
        r["value"] = float(r["value"])
    return rows


def _series(rows: list[dict], metric: str, iso3: str) -> list[tuple[int, float]]:
    pts = [(r["year"], r["value"]) for r in rows if r["metric"] == metric and r["iso3"] == iso3]
    return sorted(pts)


def _eu_mean_at(rows: list[dict], metric: str, year: int) -> Optional[float]:
    vals = [
        r["value"]
        for r in rows
        if r["metric"] == metric
        and r["year"] == year
        and countries.group_for_iso3(r["iso3"]) == countries.EU
    ]
    return statistics.fmean(vals) if vals else None


def build_summary(rows: list[dict]) -> list[dict]:
    summary: list[dict] = []
    for metric_id, meta in metrics.METRICS.items():
        uk = _series(rows, metric_id, countries.UK_ISO3)
        if not uk:
            continue
        (y0, v0), (y1, v1) = uk[0], uk[-1]
        change = v1 - v0
        if y1 == y0:
            direction = "single year"
        elif abs(change) < 1e-9:
            direction = "flat"
        else:
            direction = "rising" if change > 0 else "falling"

        us = [v for (yy, v) in _series(rows, metric_id, "USA") if yy == y1]
        summary.append({
            "metric": metric_id,
            "label": meta.label,
            "unit": meta.unit,
            "family": meta.family,
            "uk_first_year": y0,
            "uk_first_value": round(v0, 3),
            "uk_latest_year": y1,
            "uk_latest_value": round(v1, 3),
            "uk_change": round(change, 3),
            "uk_direction": direction,
            "eu27_mean_latest": (
                None if (m := _eu_mean_at(rows, metric_id, y1)) is None else round(m, 3)
            ),
            "us_latest": round(us[0], 3) if us else None,
        })
    return summary


def _fmt(v) -> str:
    return "n/a" if v is None else f"{v:g}"


def print_table(summary: list[dict]) -> None:
    header = (
        f"{'Metric':<30} {'Span':<11} {'UK first':>9} {'UK latest':>10} "
        f"{'Change':>8} {'Trend':>8} {'EU-27':>8} {'US':>8}"
    )
    print("\n" + header)
    print("-" * len(header))
    for r in summary:
        span = f"{r['uk_first_year']}-{r['uk_latest_year']}"
        print(
            f"{r['label']:<30} {span:<11} {_fmt(r['uk_first_value']):>9} "
            f"{_fmt(r['uk_latest_value']):>10} {_fmt(r['uk_change']):>8} "
            f"{r['uk_direction']:>8} {_fmt(r['eu27_mean_latest']):>8} {_fmt(r['us_latest']):>8}"
        )


def print_verdict(summary: list[dict]) -> None:
    survey = next((r for r in summary if r["metric"] == "trust_national_govt_pct"), None)
    print("\nUK trust in government - read:")
    if survey:
        print(
            f"  Survey trust in national government: {survey['uk_latest_value']:g}% "
            f"in {survey['uk_latest_year']} ({survey['uk_direction']} since "
            f"{survey['uk_first_year']}, {survey['uk_change']:+g} pts)."
        )
        if survey["eu27_mean_latest"] is not None:
            gap = survey["uk_latest_value"] - survey["eu27_mean_latest"]
            print(
                f"    vs EU-27 mean {survey['eu27_mean_latest']:g}% "
                f"(UK is {abs(gap):g} pts {'higher' if gap >= 0 else 'lower'})."
            )
    gov = [r for r in summary if r["family"] == "governance"]
    falling = [r["label"] for r in gov if r["uk_direction"] == "falling"]
    if gov:
        print(
            f"  WGI governance quality: {len(falling)}/{len(gov)} indicators lower than at "
            f"the start of the series"
            + (f" ({', '.join(falling)})." if falling else ".")
        )


def main(source: str | None = None) -> None:
    rows = load_rows(source)
    summary = build_summary(rows)
    if not summary:
        print("[summary] no UK rows found; run fetch_trust.py first.")
        return
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    with open(SUMMARY_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)
    print(f"[summary] wrote {SUMMARY_CSV}")
    print_table(summary)
    print_verdict(summary)


if __name__ == "__main__":
    main()
