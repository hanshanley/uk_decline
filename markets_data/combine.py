"""Fetch the World Bank stock-market-size rows and write tidy long/wide CSVs.

Exposes ``build(start, end, csv)`` which fetches, writes ``data/stock_market_size.csv``
(long), a wide one-row-per-region-year CSV, and a run manifest, returning the long
DataFrame for reuse by the chart/summary steps.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Iterable

from . import markets, worldbank
from .paths import DEFAULT_CSV, DEFAULT_MANIFEST, DEFAULT_WIDE_CSV

METRIC_ORDER = list(markets.METRICS)


def fetch_all(
    start: int | None = None,
    end: int | None = None,
    codes: Iterable[str] | None = None,
) -> list[dict]:
    """Fetch tidy rows from the World Bank. Failures are logged, not fatal."""
    start = start if start is not None else 1975
    end = end if end is not None else _dt.date.today().year
    try:
        rows = worldbank.fetch(start, end, codes=codes)
    except Exception as exc:  # noqa: BLE001 - resilience: still emit what we have
        print(f"[markets_data] WARNING: World Bank fetch failed: {exc}", file=sys.stderr)
        return []
    print(f"[markets_data] World Bank: {len(rows)} rows", file=sys.stderr)
    return rows


def to_frame(rows: list[dict]):
    """Return a sorted pandas DataFrame with the canonical column order."""
    import pandas as pd

    df = pd.DataFrame(rows, columns=list(markets.ROW_FIELDS))
    if not df.empty:
        df = df.sort_values(["metric", "region_code", "year"]).reset_index(drop=True)
    return df


def to_wide(df):
    """Pivot the long frame to one row per (region, year), one column per metric."""
    import pandas as pd

    if df.empty:
        return pd.DataFrame(columns=["region", "region_code", "year", *METRIC_ORDER])
    wide = (
        df.pivot_table(
            index=["region", "region_code", "year"],
            columns="metric",
            values="value",
            aggfunc="first",
        )
        .reset_index()
    )
    for m in METRIC_ORDER:
        if m not in wide.columns:
            wide[m] = pd.NA
    wide = wide[["region", "region_code", "year", *METRIC_ORDER]]
    wide.columns.name = None
    return wide.sort_values(["region", "year"]).reset_index(drop=True)


def write_manifest(df, path: Path | str = DEFAULT_MANIFEST, extra: dict | None = None) -> Path:
    path = Path(path)
    years = df["year"].tolist() if not df.empty else []
    manifest = {
        "generated_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "n_rows": int(len(df)),
        "year_min": int(min(years)) if years else None,
        "year_max": int(max(years)) if years else None,
        "regions": sorted(df["region"].unique().tolist()) if not df.empty else [],
        "metrics": sorted(df["metric"].unique().tolist()) if not df.empty else [],
        "sources": sorted(df["source"].unique().tolist()) if not df.empty else [],
    }
    if extra:
        manifest.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=2)
    return path


def build(
    start: int | None = None,
    end: int | None = None,
    path: Path | str = DEFAULT_CSV,
    wide_path: Path | str = DEFAULT_WIDE_CSV,
    manifest_path: Path | str = DEFAULT_MANIFEST,
):
    """Fetch, write long + wide CSVs and a manifest. Returns the long DataFrame."""
    rows = fetch_all(start, end)
    df = to_frame(rows)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"[markets_data] wrote {len(df)} rows -> {path}", file=sys.stderr)

    wide = to_wide(df)
    wide.to_csv(wide_path, index=False)
    print(f"[markets_data] wrote {len(wide)} region-years -> {wide_path}", file=sys.stderr)

    mpath = write_manifest(
        df,
        manifest_path,
        extra={"requested_start": start, "requested_end": end},
    )
    print(f"[markets_data] wrote manifest -> {mpath}", file=sys.stderr)
    return df
