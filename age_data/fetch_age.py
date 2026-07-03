#!/usr/bin/env python3
"""Fetch UK-vs-US-vs-Europe age-distribution data from the free World Bank WDI API.

Pulls the population-ageing story and writes tidy long + wide CSVs and a manifest into the
output directory, then prints a short UK vs Europe-median vs US summary and renders charts:

  * broad structure -> share aged 0-14 / 15-64 / 65+ and old-age/child dependency ratios
  * pyramids        -> 5-year age-band shares by sex (for UK population pyramids over time)
  * median age      -> DERIVED transparently from the 5-year band counts (labelled as such)

Data is collected by the UN Population Division (World Population Prospects) and
redistributed by the World Bank (see README_age.md / data/age_manifest.json citations).

Examples:
    python fetch_age.py                        # all sources, 1960-current
    python fetch_age.py --start 1960 --end 2024
    python fetch_age.py --sources structure    # skip pyramids/median age
    python fetch_age.py --no-charts
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

from tqdm import tqdm

from age_data import charts, combine, config, fallback, median_age, pyramids, worldbank

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOURCES = ("structure", "pyramids")  # median age is derived from pyramids, not fetched


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch UK vs US vs Europe age-distribution data (World Bank WDI, no key).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--start", type=int, default=1960, help="First year (inclusive).")
    p.add_argument(
        "--end", type=int, default=dt.date.today().year, help="Last year (inclusive)."
    )
    p.add_argument(
        "--sources",
        nargs="+",
        choices=SOURCES,
        default=list(SOURCES),
        help="Which data sources to fetch (median age is derived when 'pyramids' runs).",
    )
    p.add_argument("--out", default=os.path.join(_REPO_ROOT, "data"), help="Output directory for CSVs.")
    p.add_argument(
        "--charts-dir", default=os.path.join(_REPO_ROOT, "outputs", "age"),
        help="Directory for the rendered Substack-style charts (committable).",
    )
    p.add_argument("--charts", dest="charts", action="store_true", default=True,
                   help="Render Substack-style charts into --charts-dir.")
    p.add_argument("--no-charts", dest="charts", action="store_false",
                   help="Skip chart rendering.")
    p.add_argument(
        "--summary-year", type=int, default=None,
        help="Year for the printed UK/Europe/US summary (default: latest with data).",
    )
    return p.parse_args(argv)


def _print_summary(all_rows: list[dict], year: int | None) -> None:
    from age_data import stats

    rows = [r for r in stats.summarize(all_rows, year=year) if not r["age_band"]]
    if not rows:
        print("\n(no data available for a summary)")
        return
    print("\nUK vs Europe (median) vs US — age distribution:")
    header = f"  {'metric':<28} {'year':>4}  {'UK':>8} {'EU med':>8} {'EU avg':>8} {'US':>8}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    def fmt(v, unit):
        if v is None:
            return "     -  "
        return f"{v:6.1f}%" if unit == "percent" else f"{v:7.1f} "

    for r in rows:
        print(
            f"  {r['metric']:<28} {r['year']:>4}  "
            f"{fmt(r['uk'], r['unit'])} {fmt(r['europe_median'], r['unit'])} "
            f"{fmt(r['europe_mean'], r['unit'])} {fmt(r['us'], r['unit'])}"
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.start > args.end:
        print("error: --start must be <= --end", file=sys.stderr)
        return 2

    manual: list[dict] | None = None
    grouped: list[tuple[str, list[dict]]] = []
    all_rows: list[dict] = []

    def with_fallback(name: str, rows: list[dict], owned: tuple[str, ...]) -> list[dict]:
        nonlocal manual
        if rows:
            return rows
        if manual is None:
            manual = fallback.load()
        scoped = [r for r in manual if r["metric"] in owned]
        if scoped:
            tqdm.write(f"  {name}: using manual fallback ({len(scoped)} rows)")
        return scoped

    for name in tqdm(args.sources, desc="sources", unit="src"):
        if name == "structure":
            try:
                rows = worldbank.fetch(args.start, args.end)
            except Exception as exc:  # pragma: no cover - network failure path
                tqdm.write(f"  structure: fetch failed ({exc}); trying fallback")
                rows = []
            rows = with_fallback("structure", rows, worldbank.METRICS)
            tqdm.write(f"  structure: {len(rows)} rows")
            grouped.append(("age_structure", rows))
            all_rows.extend(rows)
        elif name == "pyramids":
            try:
                prows = pyramids.fetch(args.start, args.end)
            except Exception as exc:  # pragma: no cover - network failure path
                tqdm.write(f"  pyramids: fetch failed ({exc}); trying fallback")
                prows = []
            prows = with_fallback("pyramids", prows, pyramids.METRICS)
            tqdm.write(f"  pyramids: {len(prows)} rows")
            grouped.append(("age_pyramids", prows))
            all_rows.extend(prows)
            # Median age is DERIVED from the pyramid band shares (no extra network calls).
            mrows = median_age.derive(prows)
            if not mrows:
                mrows = with_fallback("median_age", [], median_age.METRICS)
            tqdm.write(f"  median_age (derived): {len(mrows)} rows")
            grouped.append(("age_median", mrows))
            all_rows.extend(mrows)

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
        for path in charts.render_all(all_rows, args.charts_dir):
            print(f"  {'chart':15s} {path}")

    _print_summary(all_rows, args.summary_year)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
