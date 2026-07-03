"""CLI entrypoint: fetch stock-market-size data, combine, chart, and summarise.

Usage:
    python -m markets_data                      # fetch + write CSV + charts + summary
    python -m markets_data --start 1970 --end 2024
    python -m markets_data --no-charts --no-summary
    python -m markets_data --from-csv data/stock_market_size.csv

The default year span starts at 1970 (World Bank stock-market data begins 1975, so
this captures the full available history back to the 1970s).
"""

from __future__ import annotations

import argparse
import sys

from . import charts, combine, summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="markets_data", description=__doc__)
    p.add_argument(
        "--start",
        type=int,
        default=None,
        help="first calendar year (inclusive); default 1970 (data begins 1975)",
    )
    p.add_argument("--end", type=int, default=None, help="last calendar year (inclusive)")
    p.add_argument("--csv", default=str(combine.DEFAULT_CSV), help="combined long CSV path")
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
        import pandas as pd

        print(f"[markets_data] using existing CSV: {args.from_csv}", file=sys.stderr)
        source = pd.read_csv(args.from_csv)  # load once; reused by charts + summary
    else:
        df = combine.build(args.start, args.end, args.csv)
        source = df
        if df.empty:
            print("[markets_data] no rows fetched; nothing to chart/summarise", file=sys.stderr)
            return 1

    if args.charts:
        written = charts.make_charts(source)
        print(f"[markets_data] wrote {len(written)} charts", file=sys.stderr)
    if args.summary:
        path = summary.build_summary(source)
        print(f"[markets_data] wrote summary -> {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
