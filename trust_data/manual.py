"""Loader for the vendored OECD trust seed CSV.

The OECD Data API is rate-limited and occasionally unavailable, so a curated snapshot of the
OECD "trust in national government" series lives in ``data/trust/raw/manual_trust.csv``. Each
row carries its own ``source`` + ``year`` so provenance is explicit. This is the same
manual/live hybrid the repo uses for OECD tuition (see ``tuition/data/raw/manual_tuition.csv``).

The seed is used to *fill* country-years that the live OECD SDMX fetch does not return; live
rows always take precedence in :func:`trust_data.combine`.
"""

from __future__ import annotations

import csv
import os
from typing import Iterable

from . import countries, metrics

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PKG_DIR)
SEED_CSV = os.path.join(ROOT, "data", "trust", "raw", "manual_trust.csv")

# Columns expected in the seed CSV.
SEED_FIELDS = ("iso3", "year", "metric", "value", "source")


def load(path: str | None = None, iso3s: Iterable[str] | None = None) -> list[dict]:
    """Load the seed CSV into validated tidy rows; returns ``[]`` if the file is absent."""
    path = path or SEED_CSV
    if not os.path.exists(path):
        return []
    keep = set(iso3s) if iso3s is not None else set(countries.iso3_codes())

    out: list[dict] = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            iso3 = (row.get("iso3") or "").strip()
            raw_value = (row.get("value") or "").strip()
            if not iso3 or iso3 not in keep or not raw_value:
                continue
            out.append(
                metrics.make_row(
                    iso3=iso3,
                    country=countries.name_for_iso3(iso3),
                    year=int(str(row["year"])[:4]),
                    metric=(row.get("metric") or "trust_national_govt_pct").strip(),
                    value=float(raw_value),
                    source=(row.get("source") or "OECD (manual seed)").strip(),
                )
            )
    return out
