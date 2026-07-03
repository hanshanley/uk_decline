"""Combine the four nation sources into one tidy long-format table.

Each nation module exposes ``fetch(start_year, end_year) -> list[dict]`` returning
rows with the :data:`nhs_data.metrics.ROW_FIELDS` schema. This module calls them
all, concatenates the rows, and writes ``data/nhs_waiting_times.csv``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Iterable

from . import england, metrics, northern_ireland, population, scotland, wales
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


def add_per_capita(
    rows: list[dict],
    start_year: int | None = None,
    end_year: int | None = None,
) -> list[dict]:
    """Append derived ``rtt_waiting_list_per_1000`` rows from real ONS populations.

    For each ``rtt_waiting_list_total`` row we divide by that nation-year's real
    ONS mid-year population estimate and multiply by 1,000. Rows whose year has no
    published estimate are left without a per-capita value (never extrapolated).
    A failure fetching population is logged and skipped, leaving raw rows intact.
    """
    try:
        pops = population.fetch(start_year, end_year)
    except Exception as exc:  # noqa: BLE001 - population is an optional enrichment
        print(f"[nhs_data] WARNING: population source failed: {exc}", file=sys.stderr)
        return rows

    derived: list[dict] = []
    for row in rows:
        if row["metric"] != "rtt_waiting_list_total":
            continue
        year = int(str(row["date"])[:4])
        pop = pops.get((row["nation_code"], year))
        if not pop:
            continue
        derived.append(
            metrics.make_row(
                row["nation"],
                row["nation_code"],
                row["period"],
                row["date"],
                "rtt_waiting_list_per_1000",
                row["value"] / pop * 1000.0,
                f"{row['source']} / {population.SOURCE}",
            )
        )
    if derived:
        print(f"[nhs_data] per-capita: {len(derived)} rows", file=sys.stderr)
    return rows + derived


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
    rows = add_per_capita(rows, start_year, end_year)
    return write_csv(rows, path)
