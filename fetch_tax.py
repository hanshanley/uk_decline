#!/usr/bin/env python3
"""Fetch UK-vs-US-vs-Europe tax-burden data from the free OECD SDMX API.

Pulls two complementary measures and writes tidy long + wide CSVs and a manifest into
the output directory, then prints a short UK vs Europe-median vs US summary:

  * macro       -> total tax revenue as a share of GDP (OECD Revenue Statistics)
  * individual  -> labour tax wedge & net personal average tax rate at 67/100/167%
                   of the average wage, single & couple-with-2-children (Taxing Wages)

Examples:
    python fetch_tax.py                       # both sources, 2000-current
    python fetch_tax.py --start 2015 --end 2024
    python fetch_tax.py --sources taxing_wages
    python fetch_tax.py --out data
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

from tqdm import tqdm

from tax import charts, combine, fallback, revenue, stats, taxing_wages

SOURCES = ("revenue", "taxing_wages")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch UK vs US vs Europe tax-burden data (OECD SDMX, no API key).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--start", type=int, default=2000, help="First year (inclusive).")
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
    p.add_argument("--out", default="data", help="Output directory for CSVs.")
    p.add_argument(
        "--charts-dir",
        default="outputs",
        help="Directory for the rendered Substack-style charts (committable).",
    )
    p.add_argument(
        "--charts",
        dest="charts",
        action="store_true",
        default=True,
        help="Render Substack-style comparison charts into --charts-dir.",
    )
    p.add_argument(
        "--no-charts", dest="charts", action="store_false", help="Skip chart rendering."
    )
    p.add_argument(
        "--summary-year",
        type=int,
        default=None,
        help="Year for the printed UK/Europe/US summary (default: latest with data).",
    )
    return p.parse_args(argv)


def _print_summary(all_rows: list[dict], year: int | None) -> None:
    rows = stats.summarize(all_rows, year=year)
    if not rows:
        print("\n(no data available for a summary)")
        return
    print("\nUK vs Europe (median) vs US — tax burden:")
    header = f"  {'metric variant':<52} {'year':>4}  {'UK':>7} {'EU med':>7} {'EU avg':>7} {'US':>7}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    def fmt(v: float | None) -> str:
        return f"{v:6.1f}%" if v is not None else "     - "

    for r in rows:
        variant = r["metric"]
        if r["household"] or r["earnings"]:
            variant = f"{r['metric']} [{r['household']},{r['earnings']}]"
        print(
            f"  {variant:<52} {r['year']:>4}  "
            f"{fmt(r['uk'])} {fmt(r['europe_median'])} {fmt(r['europe_mean'])} {fmt(r['us'])}"
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.start > args.end:
        print("error: --start must be <= --end", file=sys.stderr)
        return 2

    # stem + the metric ids each source owns (used to scope the offline fallback so a
    # source only ever contributes its own metrics — no cross-source duplication).
    fetchers = {
        "revenue": ("tax_revenue_to_gdp", revenue.fetch, revenue.METRICS),
        "taxing_wages": ("tax_taxing_wages", taxing_wages.fetch, taxing_wages.METRICS),
    }

    manual: list[dict] | None = None  # loaded lazily, once, and reused across sources
    grouped: list[tuple[str, list[dict]]] = []
    all_rows: list[dict] = []
    for name in tqdm(args.sources, desc="sources", unit="src"):
        stem, fn, owned = fetchers[name]
        try:
            rows = fn(args.start, args.end)
        except Exception as exc:  # pragma: no cover - network failure path
            tqdm.write(f"  {name}: fetch failed ({exc}); trying fallback")
            rows = []
        if not rows:
            if manual is None:
                manual = fallback.load()
            rows = [r for r in manual if r["metric"] in owned]
            if rows:
                tqdm.write(f"  {name}: using manual fallback ({len(rows)} rows)")
        tqdm.write(f"  {name}: {len(rows)} rows")
        grouped.append((stem, rows))
        all_rows.extend(rows)

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

    if args.charts:
        chart_paths = charts.render_all(all_rows, args.charts_dir)
        for path in chart_paths:
            print(f"  {'chart':15s} {path}")

    _print_summary(all_rows, args.summary_year)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
