"""Offline fallback: load curated tax figures from ``data/raw/manual_tax.csv``.

Used only when a live OECD SDMX fetch returns no rows (e.g. offline unit tests or an
API outage), so the pipeline still produces a usable comparison. Each CSV row carries
its own ``source`` + ``year``; the ``household`` / ``earnings`` columns are blank for
the macro ``tax_to_gdp_pct`` metric.
"""

from __future__ import annotations

import csv
import os

from . import config
from .combine import make_row


def load(path: str | None = None) -> list[dict]:
    """Load fallback rows from ``manual_tax.csv``; returns ``[]`` if the file is absent."""
    path = path or config.MANUAL_CSV
    if not os.path.exists(path):
        return []

    out: list[dict] = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            iso3 = (r.get("iso3") or "").strip()
            metric = (r.get("metric") or "").strip()
            value = (r.get("value") or "").strip()
            if iso3 not in config.BY_ISO3 or metric not in config.METRICS or not value:
                continue
            out.append(
                make_row(
                    iso3=iso3,
                    year=int(r["year"]),
                    metric=metric,
                    value=float(value),
                    source=(r.get("source") or "manual").strip(),
                    household=(r.get("household") or "").strip(),
                    earnings=(r.get("earnings") or "").strip(),
                )
            )
    return out
