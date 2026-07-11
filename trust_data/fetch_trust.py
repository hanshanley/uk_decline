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

from trust_data import combine, countries, metrics, owid, worldbank

SOURCES = ("oecd", "worldbank")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch UK trust-in-government indicators over time (vs EU-27 + US).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--start", type=int, default=1974, help="First year (inclusive).")
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
    """Consistent historical trust series fetched live from OWID/OECD."""
    return owid.fetch(start, end)


def _validate_source_rows(name: str, rows: list[dict], owned: tuple[str, ...]) -> None:
    """Require every metric to contain the UK, US, and at least one EU comparator."""
    if not rows:
        raise RuntimeError(f"{name}: online source returned no rows")
    incomplete = []
    for metric in owned:
        metric_countries = {r["iso3"] for r in rows if r["metric"] == metric}
        has_europe = any(
            countries.group_for_iso3(iso3) == countries.EU
            for iso3 in metric_countries
        )
        if not {"GBR", "USA"} <= metric_countries or not has_europe:
            incomplete.append(metric)
    if incomplete:
        raise RuntimeError(
            f"{name}: incomplete online response for metrics {incomplete}"
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.start > args.end:
        print("error: --start must be <= --end", file=sys.stderr)
        return 2

    fetchers = {
        "oecd": (
            "oecd_trust_national_govt",
            lambda: _fetch_oecd(args.start, args.end),
            tuple(metrics.SURVEY_METRICS),
        ),
        "worldbank": (
            "worldbank_wgi",
            lambda: worldbank.fetch(args.start, args.end),
            tuple(metrics.GOVERNANCE_METRICS),
        ),
    }

    grouped: list[tuple[str, list[dict]]] = []
    for name in tqdm(args.sources, desc="sources", unit="src"):
        stem, fn, owned = fetchers[name]
        rows = fn()
        _validate_source_rows(name, rows, owned)
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
        from trust_data import charts, report

        paths = charts.make_charts(written["combined_long"])
        print(f"\nCharts ({len(paths)}):")
        for pth in paths:
            print(f"  {pth}")
        readme = report.write_showcase(
            args.out,
            long_csv=written["combined_long"],
            manifest_json=written["manifest"],
            chart_files=[str(p) for p in paths],
        )
        print(f"\nShowcase README (references data sources): {readme}")

    if args.summary:
        from trust_data import summary

        summary.main(written["combined_long"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
