"""Shared helpers for the nhs_data source and output modules.

Centralises the small pieces that were previously duplicated (and drifting) across
the four nation clients: default year-range resolution, a uniform stderr warning
format, calendar-year row filtering, and loading a combined table from either a
DataFrame or a CSV path.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_YEAR_SPAN = 9  # default lookback: latest ~10 calendar years (inclusive)


def year_bounds(
    start_year: int | None,
    end_year: int | None,
    span: int = DEFAULT_YEAR_SPAN,
) -> tuple[int, int]:
    """Resolve an inclusive ``(start, end)`` calendar-year range with defaults.

    ``end`` defaults to the current year and ``start`` to ``end - span``. Raises
    ``ValueError`` if the resolved ``start`` is after ``end``.
    """
    end = end_year if end_year is not None else date.today().year
    start = start_year if start_year is not None else end - span
    if start > end:
        raise ValueError(f"start_year ({start}) must be <= end_year ({end})")
    return start, end


def warn(nation_code: str, metric: str, exc: Exception) -> None:
    """Log a uniform, non-fatal source-failure warning to stderr."""
    print(f"[nhs_data] WARNING: {nation_code} {metric}: {exc}", file=sys.stderr)


def filter_rows_by_year(rows: list[dict], start_year: int, end_year: int) -> list[dict]:
    """Keep tidy rows whose ``date`` (ISO ``YYYY-...``) year is within the range."""
    return [
        row for row in rows if start_year <= int(str(row["date"])[:4]) <= end_year
    ]


def load_frame(source: Any, default_csv: Path | str):
    """Return a DataFrame from ``source`` (a DataFrame, a CSV path, or ``None``).

    ``None`` falls back to ``default_csv``; an object exposing ``columns`` is passed
    through unchanged; anything else is read as a CSV.
    """
    import pandas as pd

    if source is None:
        source = default_csv
    if hasattr(source, "columns"):
        return source
    return pd.read_csv(source)
