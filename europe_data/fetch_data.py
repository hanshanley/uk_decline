#!/usr/bin/env python3
"""Fetch European per-capita GDP (PPP) and median disposable income (PPP/PPS).

Pulls a time series across geographic Europe (with a UK focus) from free, key-less
sources and writes tidy long + wide CSVs into the output directory.

Run from the repo root as a module:
    python -m europe_data.fetch_data                      # all sources, 1970-current
    python -m europe_data.fetch_data --start 2005 --end 2024
    python -m europe_data.fetch_data --sources worldbank eurostat
    python -m europe_data.fetch_data --out data
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys

from tqdm import tqdm

from europe_data import combine, eurostat, maddison, pip, worldbank

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = ("worldbank", "maddison", "eurostat", "pip")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch European per-capita GDP (PPP) and median income (PPP/PPS).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--start", type=int, default=1970, help="First year (inclusive).")
    p.add_argument(
        "--end",
        type=int,
        default=dt.date.today().year,
        help="Last year (inclusive).",
    )
    p.add_argument(
        "--sources",
        nargs="+",
        choices=SOURCES,
        default=list(SOURCES),
        help="Which data sources to fetch.",
    )
    p.add_argument("--out", default=str(REPO_ROOT / "data"), help="Output directory for CSVs.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.start > args.end:
        print("error: --start must be <= --end", file=sys.stderr)
        return 2

    # (source_stem -> fetch callable)
    fetchers = {
        "worldbank": ("gdp_per_capita_ppp", worldbank.fetch),
        "maddison": ("gdp_per_capita_real_maddison", maddison.fetch),
        "eurostat": ("eurostat_median_income_pps", eurostat.fetch),
        "pip": ("pip_median_income", pip.fetch),
    }

    grouped: list[tuple[str, list[dict]]] = []
    for name in tqdm(args.sources, desc="sources", unit="src"):
        stem, fn = fetchers[name]
        rows = fn(args.start, args.end)
        # Add the CPI-deflated real-US$ GDP series (constant 2015 US$, market FX) alongside
        # the World Bank indicators — this is the headline GDP measure used by the charts.
        if name == "worldbank":
            cpi = worldbank.us_cpi(args.start, args.end)
            real_rows = worldbank.deflate_to_real_usd(rows, cpi)
            rows = rows + real_rows
        tqdm.write(f"  {name}: {len(rows)} rows")
        grouped.append((stem, rows))

    written = combine.combine(
        grouped,
        args.out,
        extra_manifest={
            "requested_start": args.start,
            "requested_end": args.end,
            "requested_sources": args.sources,
        },
    )

    print("\nWrote:")
    for name, path in written.items():
        print(f"  {name:15s} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
