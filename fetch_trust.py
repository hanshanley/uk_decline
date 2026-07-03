#!/usr/bin/env python3
"""Fetch trust-in-government indicators for the UK over time (vs EU-27 + US).

Pulls two complementary, free, key-less series and writes tidy long + wide CSVs (plus an
optional set of trend charts and a UK-focused summary) into the output directory:

  * OECD survey trust in national government (with a vendored manual-seed fallback)
  * World Bank Worldwide Governance Indicators (WGI)

Examples:
    python fetch_trust.py                          # all sources, 2006-current
    python fetch_trust.py --start 2010 --end 2023
    python fetch_trust.py --sources worldbank
    python fetch_trust.py --charts --summary
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys

from tqdm import tqdm

from trust_data import combine, manual, oecd, worldbank

SOURCES = ("oecd", "worldbank")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch UK trust-in-government indicators over time (vs EU-27 + US).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--start", type=int, default=2006, help="First year (inclusive).")
    p.add_argument(
        "--end", type=int, default=dt.date.today().year, help="Last year (inclusive)."
    )
    p.add_argument(
        "--sources",
        nargs="+",
        choices=SOURCES,
        default=list(SOURCES),
        help="Which data sources to fetch.",
    )
    p.add_argument("--out", default="data/trust", help="Output directory for CSVs.")
    p.add_argument("--charts", action="store_true", help="Also render trend charts.")
    p.add_argument("--summary", action="store_true", help="Also print/write the UK summary.")
    return p.parse_args(argv)


def _fetch_oecd(start: int, end: int) -> list[dict]:
    """OECD live rows, backfilled with the manual seed for any missing country-years."""
    live = oecd.fetch(start, end)
    seed = [r for r in manual.load() if start <= r["year"] <= end]
    have = {(r["iso3"], r["year"], r["metric"]) for r in live}
    filled = [r for r in seed if (r["iso3"], r["year"], r["metric"]) not in have]
    if filled:
        tqdm.write(f"  oecd: backfilled {len(filled)} rows from manual seed")
    return live + filled


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.start > args.end:
        print("error: --start must be <= --end", file=sys.stderr)
        return 2

    fetchers = {
        "oecd": ("oecd_trust_national_govt", lambda: _fetch_oecd(args.start, args.end)),
        "worldbank": ("worldbank_wgi", lambda: worldbank.fetch(args.start, args.end)),
    }

    grouped: list[tuple[str, list[dict]]] = []
    for name in tqdm(args.sources, desc="sources", unit="src"):
        stem, fn = fetchers[name]
        rows = fn()
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
        print(f"  {name:22s} {path}")

    if args.charts:
        from trust_data import charts

        paths = charts.make_charts(written["combined_long"])
        print(f"\nCharts ({len(paths)}):")
        for pth in paths:
            print(f"  {pth}")

    if args.summary:
        from trust_data import summary

        summary.main(written["combined_long"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
