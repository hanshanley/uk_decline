"""Shared loader for the processed per-country tuition dataset.

Used by both ``analyze.py`` and ``plot_tuition.py`` so they apply an identical
primary-row filter (:func:`tuition.config.is_primary`) and value coercion — keeping the
reported statistics and the figures in sync.
"""

from __future__ import annotations

import csv
from typing import Iterable, Optional

from . import config

_NULLS = ("", "None", None)


def load_primary(value_keys: Iterable[str], path: Optional[str] = None) -> list[dict]:
    """Load primary (headline) per-country rows, coercing ``value_keys`` to float/None."""
    value_keys = list(value_keys)  # materialize: iterated once per row
    path = path or config.TUITION_BY_COUNTRY_CSV
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    out: list[dict] = []
    for r in rows:
        if not config.is_primary(r):
            continue
        for key in value_keys:
            r[key] = None if r.get(key) in _NULLS else float(r[key])
        out.append(r)
    return out
