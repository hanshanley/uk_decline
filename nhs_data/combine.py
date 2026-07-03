"""Combine the four nation sources into one tidy long-format table.

Each nation module exposes ``fetch(start_year, end_year) -> list[dict]`` returning
rows with the :data:`nhs_data.metrics.ROW_FIELDS` schema. This module calls them
all, concatenates the rows, and writes ``data/nhs_waiting_times.csv``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Iterable

from . import england, metrics, northern_ireland, scotland, wales
from .paths import DEFAULT_CSV

# nation code -> fetch callable
SOURCES: dict[str, Callable[..., list[dict]]] = {
    "ENG": england.fetch,
    "SCO": scotland.fetch,
    "WAL": wales.fetch,
    "NIR": northern_ireland.fetch,
}


def fetch_all(
    start_year: int | None = None,
    end_year: int | None = None,
    codes: Iterable[str] | None = None,
) -> list[dict]:
    """Fetch and concatenate tidy rows from all (or the selected) nations.

    A failure in one nation source is logged and skipped rather than aborting the
    whole run, so partial data is still produced.
    """
    wanted = list(codes) if codes is not None else list(SOURCES)
    rows: list[dict] = []
    for code in wanted:
        fetch = SOURCES[code]
        try:
            got = fetch(start_year, end_year)
        except Exception as exc:  # noqa: BLE001 - resilience across heterogeneous sources
            print(f"[nhs_data] WARNING: {code} source failed: {exc}", file=sys.stderr)
            continue
        print(f"[nhs_data] {code}: {len(got)} rows", file=sys.stderr)
        rows.extend(got)
    return rows


def to_frame(rows: list[dict]):
    """Return a sorted pandas DataFrame with the canonical column order."""
    import pandas as pd

    df = pd.DataFrame(rows, columns=list(metrics.ROW_FIELDS))
    if not df.empty:
        df = df.sort_values(["metric", "nation_code", "date"]).reset_index(drop=True)
    return df


def write_csv(rows: list[dict], path: Path | str = DEFAULT_CSV):
    """Write tidy rows to ``path`` (creating parent dirs) and return the DataFrame."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = to_frame(rows)
    df.to_csv(path, index=False)
    print(f"[nhs_data] wrote {len(df)} rows -> {path}", file=sys.stderr)
    return df


def build(
    start_year: int | None = None,
    end_year: int | None = None,
    path: Path | str = DEFAULT_CSV,
):
    """Fetch all nations and write the combined CSV. Returns the DataFrame."""
    rows = fetch_all(start_year, end_year)
    return write_csv(rows, path)
