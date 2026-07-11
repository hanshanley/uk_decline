"""Combine tidy trust rows from all sources into long + wide CSVs and a run manifest.

Adapted from ``europe_data/combine.py``. Rows follow
:data:`trust_data.metrics.ROW_FIELDS`. When two sources report the same
``(iso3, year, metric)`` the first row wins - callers pass direct OECD SDMX rows before the
live OWID/OECD historical series (see :func:`dedupe`).
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import os
from typing import Iterable

from .metrics import GOVERNANCE_METRICS, ROW_FIELDS, SURVEY_METRICS

LONG_FIELDS = list(ROW_FIELDS)

# Wide-table column order (one row per country-year): survey first, then governance.
METRIC_ORDER = [*SURVEY_METRICS, *GOVERNANCE_METRICS]


def dedupe(rows: Iterable[dict]) -> list[dict]:
    """Drop duplicate ``(iso3, year, metric)`` rows, keeping the first occurrence."""
    seen: set[tuple[str, int, str]] = set()
    out: list[dict] = []
    for r in rows:
        key = (r["iso3"], int(r["year"]), r["metric"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def write_long(rows: list[dict], path: str) -> None:
    rows_sorted = sorted(rows, key=lambda r: (r["country"], r["year"], r["metric"]))
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=LONG_FIELDS)
        writer.writeheader()
        for r in rows_sorted:
            writer.writerow({k: r[k] for k in LONG_FIELDS})


def write_wide(rows: list[dict], path: str) -> None:
    # (iso3, country, year) -> {metric: value}
    table: dict[tuple[str, str, int], dict[str, float]] = {}
    for r in rows:
        key = (r["iso3"], r["country"], int(r["year"]))
        table.setdefault(key, {})[r["metric"]] = r["value"]

    header = ["iso3", "country", "year", *METRIC_ORDER]
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for (iso3, country, year) in sorted(table, key=lambda k: (k[1], k[2])):
            values = table[(iso3, country, year)]
            writer.writerow(
                [iso3, country, year, *[values.get(m, "") for m in METRIC_ORDER]]
            )


def write_manifest(rows: list[dict], path: str, extra: dict | None = None) -> None:
    years = [int(r["year"]) for r in rows]
    manifest = {
        "generated_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "n_rows": len(rows),
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
        "countries": sorted({r["country"] for r in rows}),
        "metrics": sorted({r["metric"] for r in rows}),
        "sources": sorted({r["source"] for r in rows}),
    }
    if extra:
        manifest.update(extra)
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=2)


def write_source_csv(rows: list[dict], path: str) -> None:
    """Write a single source's tidy rows to its own long CSV."""
    write_long(rows, path)


def combine(
    grouped: Iterable[tuple[str, list[dict]]],
    out_dir: str,
    extra_manifest: dict | None = None,
) -> dict[str, str]:
    """Write per-source CSVs plus combined long/wide CSVs and a manifest.

    ``grouped`` is an iterable of ``(source_filename_stem, rows)`` pairs. Rows are de-duplicated
    across all sources on ``(iso3, year, metric)`` (earlier groups win). Returns a mapping of
    logical name -> written file path.
    """
    os.makedirs(out_dir, exist_ok=True)
    all_rows: list[dict] = []
    written: dict[str, str] = {}

    for stem, rows in grouped:
        path = os.path.join(out_dir, f"{stem}.csv")
        write_source_csv(rows, path)
        written[stem] = path
        all_rows.extend(rows)

    all_rows = dedupe(all_rows)

    long_path = os.path.join(out_dir, "trust_combined_long.csv")
    wide_path = os.path.join(out_dir, "trust_combined_wide.csv")
    manifest_path = os.path.join(out_dir, "manifest.json")
    write_long(all_rows, long_path)
    write_wide(all_rows, wide_path)
    write_manifest(all_rows, manifest_path, extra=extra_manifest)

    written["combined_long"] = long_path
    written["combined_wide"] = wide_path
    written["manifest"] = manifest_path
    return written
