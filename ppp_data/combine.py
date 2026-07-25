"""Combine tidy PPP rows into long + wide CSVs and a run manifest.

Follows the repository-wide schema: a long CSV with
``iso3, country, year, metric, value, unit, source``, a wide pivot with one row per
country-year, and a JSON manifest recording coverage and provenance.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from pathlib import Path

from . import metrics, paths

LONG_FIELDS = ["iso3", "country", "year", "metric", "value", "unit", "source"]


def write_long(rows: list[dict], path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda r: (r["country"], r["year"], r["metric"]))
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=LONG_FIELDS)
        writer.writeheader()
        for row in ordered:
            writer.writerow({k: row[k] for k in LONG_FIELDS})
    return path


def write_wide(rows: list[dict], path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table: dict[tuple[str, str, int], dict[str, float]] = {}
    for row in rows:
        key = (row["iso3"], row["country"], row["year"])
        table.setdefault(key, {})[row["metric"]] = row["value"]

    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["iso3", "country", "year", *metrics.METRIC_ORDER])
        for key in sorted(table, key=lambda k: (k[1], k[2])):
            values = table[key]
            writer.writerow([*key, *[values.get(m, "") for m in metrics.METRIC_ORDER]])
    return path


def write_manifest(rows: list[dict], path: Path | str, extra: dict | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    years = [r["year"] for r in rows]
    manifest = {
        "generated_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "n_rows": len(rows),
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
        "countries": sorted({r["country"] for r in rows}),
        "metrics": sorted({r["metric"] for r in rows}),
        "sources": sorted({r["source"] for r in rows}),
        "ppp_vintage": metrics.ICP_VINTAGE,
        "caveats": metrics.CAVEATS,
    }
    if extra:
        manifest.update(extra)
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=2)
    return path


def write_all(rows: list[dict], extra_manifest: dict | None = None) -> dict[str, Path]:
    """Write the long CSV, the wide CSV, and the manifest. Returns their paths."""
    return {
        "long": write_long(rows, paths.LONG_CSV),
        "wide": write_wide(rows, paths.WIDE_CSV),
        "manifest": write_manifest(rows, paths.MANIFEST, extra=extra_manifest),
    }


def load_long(path: Path | str | None = None) -> list[dict]:
    """Read a long CSV back into tidy rows with numeric ``year``/``value``."""
    path = Path(path) if path is not None else paths.LONG_CSV
    with open(path, newline="") as fh:
        return [
            {**row, "year": int(row["year"]), "value": float(row["value"])}
            for row in csv.DictReader(fh)
            if row.get("value") not in (None, "")
        ]
