"""Streaming aggregation helpers for the Home Office detailed-dataset spreadsheets.

These sheets are long and tidy (one observation per row, a leading ``Year``/``Quarter``
pair and a numeric measure in the last used column). We stream them and sum a measure by
``(year, category)`` while tracking which quarters each year contains, so partial trailing
years (e.g. a year with only Q1 published) can be dropped from annual series.
"""

from __future__ import annotations

import re
from typing import Callable, Iterable

_QUARTER = re.compile(r"Q([1-4])")


def _to_int_year(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_number(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _quarter_num(value) -> int | None:
    if isinstance(value, str):
        m = _QUARTER.search(value)
        if m:
            return int(m.group(1))
    return None


def aggregate_by_year(
    rows: Iterable[tuple],
    *,
    header_rows: int,
    year_idx: int,
    quarter_idx: int,
    value_idx: int,
    category_of: Callable[[tuple], str | None],
    complete_years_only: bool = True,
) -> list[tuple[int, str, float]]:
    """Sum ``value_idx`` by ``(year, category)`` over ``rows``.

    ``category_of(row)`` returns the category label, or ``None`` to skip the row.
    When ``complete_years_only`` is set, any ``(year, category)`` pair lacking all four
    quarters is dropped (removing partial figures, including the most-recent year, and
    correctly handling categories/methods whose quarterly coverage differs).

    Returns a list of ``(year, category, total)`` sorted by ``(category, year)``.
    """
    totals: dict[tuple[int, str], float] = {}
    quarters: dict[tuple[int, str], set[int]] = {}

    for i, row in enumerate(rows):
        if i < header_rows:
            continue
        year = _to_int_year(row[year_idx])
        if year is None:
            continue
        category = category_of(row)
        if category is None:
            continue
        value = _to_number(row[value_idx])
        if value is None:
            continue
        key = (year, category)
        totals[key] = totals.get(key, 0.0) + value
        q = _quarter_num(row[quarter_idx])
        if q is not None:
            quarters.setdefault(key, set()).add(q)

    if complete_years_only:
        totals = {k: v for k, v in totals.items() if len(quarters.get(k, ())) >= 4}

    return sorted(
        ((y, c, v) for (y, c), v in totals.items()), key=lambda t: (t[1], t[0])
    )
