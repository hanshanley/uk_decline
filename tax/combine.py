"""Tidy-row schema + combine tidy rows from all sources into long + wide CSVs.

Long schema (one row per country-year-metric-variant)::

    iso3, country, region, year, metric, household, earnings, value, unit, source

Macro rows (tax-to-GDP) leave ``household`` / ``earnings`` empty; individual rows
(tax wedge, net personal average tax rate) carry the variant. The wide table pivots to
one row per country-year with a column per metric variant (see :func:`config.variant_key`).
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import os
from typing import Any, Iterable

from . import config

LONG_FIELDS = [
    "iso3",
    "country",
    "region",
    "year",
    "metric",
    "household",
    "earnings",
    "value",
    "unit",
    "source",
]


def make_row(
    iso3: str,
    year: int,
    metric: str,
    value: float,
    source: str,
    household: str = "",
    earnings: str = "",
) -> dict[str, Any]:
    """Build a validated tidy row, deriving country/region/unit from lookup tables."""
    if metric not in config.METRICS:
        raise KeyError(f"unknown metric id: {metric!r}")
    return {
        "iso3": iso3,
        "country": config.name_for_iso3(iso3),
        "region": config.region_for_iso3(iso3),
        "year": int(year),
        "metric": metric,
        "household": household,
        "earnings": earnings,
        "value": float(value),
        "unit": config.METRICS[metric].unit,
        "source": source,
    }


def write_long(rows: list[dict], path: str) -> None:
    rows_sorted = sorted(
        rows,
        key=lambda r: (r["country"], r["year"], r["metric"], r["household"], r["earnings"]),
    )
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=LONG_FIELDS)
        writer.writeheader()
        for r in rows_sorted:
            writer.writerow({k: r[k] for k in LONG_FIELDS})


def _variant_columns(rows: Iterable[dict]) -> list[str]:
    """Deterministic wide-column order: macro metrics first, then individual variants."""
    cols = {config.variant_key(r["metric"], r["household"], r["earnings"]) for r in rows}
    family_rank = {"macro": 0, "individual": 1}

    def sort_key(col: str) -> tuple:
        metric = col.split("__", 1)[0]
        fam = config.METRICS[metric].family if metric in config.METRICS else "individual"
        return (family_rank.get(fam, 9), col)

    return sorted(cols, key=sort_key)


def write_wide(rows: list[dict], path: str) -> None:
    columns = _variant_columns(rows)
    table: dict[tuple[str, str, str, int], dict[str, float]] = {}
    for r in rows:
        key = (r["iso3"], r["country"], r["region"], r["year"])
        col = config.variant_key(r["metric"], r["household"], r["earnings"])
        table.setdefault(key, {})[col] = r["value"]

    header = ["iso3", "country", "region", "year", *columns]
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for (iso3, country, region, year) in sorted(table, key=lambda k: (k[1], k[3])):
            metrics = table[(iso3, country, region, year)]
            writer.writerow(
                [iso3, country, region, year, *[metrics.get(c, "") for c in columns]]
            )


def write_manifest(rows: list[dict], path: str, extra: dict | None = None) -> None:
    years = [r["year"] for r in rows]
    metrics = sorted({r["metric"] for r in rows})
    manifest = {
        "generated_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "n_rows": len(rows),
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
        "countries": sorted({r["country"] for r in rows}),
        "metrics": metrics,
        "sources": sorted({r["source"] for r in rows}),
        "caveats": {m: config.CAVEATS.get(m, "") for m in metrics},
        "citations": config.CITATIONS,
    }
    if extra:
        manifest.update(extra)
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=2)


def _dedupe(rows: list[dict]) -> list[dict]:
    """Drop duplicate observations for the same country-year-metric-variant.

    Live and offline-fallback rows can overlap for a metric a source owns; keep the
    first (live) row so the long and wide tables never disagree on a value.
    """
    seen: set[tuple] = set()
    out: list[dict] = []
    for r in rows:
        key = (r["iso3"], r["year"], r["metric"], r["household"], r["earnings"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def combine(
    grouped: Iterable[tuple[str, list[dict]]],
    out_dir: str,
    extra_manifest: dict | None = None,
) -> dict[str, str]:
    """Write per-source CSVs plus combined long/wide CSVs and a manifest.

    ``grouped`` is an iterable of ``(source_filename_stem, rows)`` pairs. Outputs are
    ``tax_``-prefixed so they never collide with ``europe_combined_*`` in ``data/``.
    Returns a mapping of logical name -> written file path.
    """
    os.makedirs(out_dir, exist_ok=True)
    all_rows: list[dict] = []
    written: dict[str, str] = {}

    for stem, rows in grouped:
        path = os.path.join(out_dir, f"{stem}.csv")
        write_long(rows, path)
        written[stem] = path
        all_rows.extend(rows)

    all_rows = _dedupe(all_rows)
    long_path = os.path.join(out_dir, "tax_combined_long.csv")
    wide_path = os.path.join(out_dir, "tax_combined_wide.csv")
    manifest_path = os.path.join(out_dir, "tax_manifest.json")
    write_long(all_rows, long_path)
    write_wide(all_rows, wide_path)
    write_manifest(all_rows, manifest_path, extra=extra_manifest)

    written["combined_long"] = long_path
    written["combined_wide"] = wide_path
    written["manifest"] = manifest_path
    return written
