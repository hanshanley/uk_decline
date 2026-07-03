"""Offline fallback: load curated age figures from ``data/raw/manual_age.csv``.

Used only when a live World Bank fetch returns no rows. The CSV is a **verifiable snapshot
of the live WB data** (not hand-authored): each row keeps its World Bank ``source`` + year,
and ``age_band`` / ``sex`` are blank for non-pyramid metrics.
"""

from __future__ import annotations

import csv
import os

from . import config
from .combine import make_row


def load(path: str | None = None) -> list[dict]:
    """Load fallback rows from ``manual_age.csv``; returns ``[]`` if the file is absent."""
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
                    source=(r.get("source") or config.SOURCE_WB).strip(),
                    age_band=(r.get("age_band") or "").strip(),
                    sex=(r.get("sex") or "").strip(),
                )
            )
    return out
