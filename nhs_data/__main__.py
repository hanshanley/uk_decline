"""CLI entrypoint: fetch NHS waiting-time data, combine, chart, and summarise.

Usage:
    python -m nhs_data                      # fetch + write CSV + charts + summary
    python -m nhs_data --start 2015 --end 2025
    python -m nhs_data --no-charts --no-summary
    python -m nhs_data --from-csv data/nhs_waiting_times.csv --charts --summary
"""

from __future__ import annotations

import argparse
import sys

from . import charts, combine, summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nhs_data", description=__doc__)
    p.add_argument("--start", type=int, default=None, help="first calendar year (inclusive)")
    p.add_argument("--end", type=int, default=None, help="last calendar year (inclusive)")
    p.add_argument("--csv", default=str(combine.DEFAULT_CSV), help="combined CSV output path")
    p.add_argument(
        "--from-csv",
        default=None,
        help="skip fetching; build charts/summary from an existing combined CSV",
    )
    p.add_argument("--no-charts", dest="charts", action="store_false", help="skip charts")
    p.add_argument("--no-summary", dest="summary", action="store_false", help="skip summary")
    p.set_defaults(charts=True, summary=True)
    args = p.parse_args(argv)

    if args.from_csv:
        source = args.from_csv
        print(f"[nhs_data] using existing CSV: {source}", file=sys.stderr)
    else:
        df = combine.build(args.start, args.end, args.csv)
        source = df
        if df.empty:
            print("[nhs_data] no rows fetched; nothing to chart/summarise", file=sys.stderr)
            return 1

    if args.charts:
        written = charts.make_charts(source)
        print(f"[nhs_data] wrote {len(written)} charts", file=sys.stderr)
    if args.summary:
        path = summary.build_summary(source)
        print(f"[nhs_data] wrote summary -> {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
