"""Fetch every UK immigration source, write per-source raw CSVs and a combined long CSV."""

from __future__ import annotations

import csv
from pathlib import Path

from . import schema
from .sources import asylum, irregular, ons_ltim, visas, worldbank

# name -> fetch callable
SOURCES = {
    "worldbank": worldbank.fetch,
    "ons_ltim": ons_ltim.fetch,
    "visas": visas.fetch,
    "asylum": asylum.fetch,
    "irregular": irregular.fetch,
}

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
COMBINED_CSV = PROCESSED_DIR / "uk_migration_long.csv"


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(schema.FIELDS))
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (r["metric"], r["category"], r["period"])):
            writer.writerow(row)


def fetch_all(only: list[str] | None = None) -> dict[str, list[dict]]:
    """Fetch selected sources, returning ``{name: rows}`` and writing ``data/raw/<name>.csv``."""
    names = only or list(SOURCES)
    results: dict[str, list[dict]] = {}
    for name in names:
        rows = SOURCES[name]()
        results[name] = rows
        _write_csv(RAW_DIR / f"{name}.csv", rows)
    return results


def combine(results: dict[str, list[dict]]) -> list[dict]:
    """Merge per-source rows into one long table and write ``uk_migration_long.csv``."""
    combined: list[dict] = []
    for rows in results.values():
        combined.extend(rows)
    _write_csv(COMBINED_CSV, combined)
    return combined


def run(only: list[str] | None = None) -> list[dict]:
    """Fetch everything and write both raw and combined CSVs."""
    return combine(fetch_all(only))
